import logging
from typing import Optional, List, Dict
from momentum_screener.schwab.http_client import (
    get_quotes,
    get_movers,
    get_price_history_every_minute,
    get_price_history_every_day,
    get_instruments
)
from schwab.client import Client

log = logging.getLogger(__name__)

def _get_tradingview_candidates() -> Dict[str, Dict]:
    """
    Fetches active/gaining tickers from TradingView along with their metadata.
    Looks at regular session gainers, pre-market gainers, and post-market gainers.
    """
    url = "https://scanner.tradingview.com/america/scan"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    candidates = {}
    
    # 1. Regular gainers
    payload_reg = {
        "filter": [
            {"left": "change", "operation": "greater", "right": 5},
            {"left": "volume", "operation": "greater", "right": 50000},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "sort": {"sortBy": "change", "sortOrder": "desc"},
        "columns": ["name", "change", "close", "volume", "market_cap_basic", "float_shares_outstanding", "sector"],
        "range": [0, 100]
    }
    
    # 2. Premarket gainers
    payload_pre = {
        "filter": [
            {"left": "premarket_change", "operation": "greater", "right": 5},
            {"left": "premarket_volume", "operation": "greater", "right": 10000},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "sort": {"sortBy": "premarket_change", "sortOrder": "desc"},
        "columns": ["name", "premarket_change", "premarket_close", "premarket_volume", "market_cap_basic", "float_shares_outstanding", "sector"],
        "range": [0, 100]
    }
    
    # 3. Postmarket gainers
    payload_post = {
        "filter": [
            {"left": "postmarket_change", "operation": "greater", "right": 5},
            {"left": "postmarket_volume", "operation": "greater", "right": 10000},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "sort": {"sortBy": "postmarket_change", "sortOrder": "desc"},
        "columns": ["name", "postmarket_change", "postmarket_close", "postmarket_volume", "market_cap_basic", "float_shares_outstanding", "sector"],
        "range": [0, 100]
    }
    
    import requests
    for label, payload in [("Regular", payload_reg), ("Pre-market", payload_pre), ("Post-market", payload_post)]:
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                rows = resp.json().get("data", [])
                log.info(f"[TradingView] {label} returned {len(rows)} candidates")
                for r in rows:
                    d = r.get("d", [])
                    sym = d[0]
                    if sym and len(sym) <= 5:  # skip warrants/long weird symbols
                        sym = sym.upper()
                        change = d[1] or 0
                        close = d[2] or 0
                        volume = d[3] or 0
                        mcap = d[4]
                        float_sh = d[5]
                        sector = d[6]
                        
                        # Update or add if change is higher
                        if sym not in candidates or abs(change) > abs(candidates[sym]["change"]):
                            candidates[sym] = {
                                "change": change,
                                "price": close,
                                "volume": volume,
                                "market_cap": mcap,
                                "float_shares": float_sh,
                                "sector": sector
                            }
            else:
                log.warning(f"[TradingView] {label} failed: {resp.status_code}")
        except Exception as e:
            log.warning(f"[TradingView] {label} error: {e}")
            
    return candidates

def get_gainers_snapshot(include_otc: bool = False) -> List[Dict]:
    """
    Simulates Polygon's gainer snapshot using a hybrid strategy:
    1. Fetch candidate tickers from TradingView (covering pre, regular, and post sessions).
    2. Fetch movers from Schwab (/movers endpoint for NYSE, NASDAQ, and EQUITY_ALL) and merge them.
    3. Fetch watchlist tickers from the local DB and merge them.
    4. Ensure all watchlist tickers are included, then fill the remaining slots up to a limit of 150 candidates with the top movers.
    5. Bulk fetch quotes from Schwab in chunks of 50.
    """
    candidate_data = {}
    
    # 1. Fetch TradingView candidates
    try:
        candidate_data = _get_tradingview_candidates()
    except Exception as e:
        log.warning(f"[Schwab Client] Failed to fetch candidates from TradingView: {e}")
    
    # 2. Fetch Schwab Movers and merge
    try:
        movers_raw = []
        for exch in ['NASDAQ', 'NYSE', 'EQUITY_ALL']:
            try:
                movers_raw.extend(get_movers(exch))
            except Exception as exch_err:
                log.warning(f"[Schwab Client] Failed to fetch movers for {exch}: {exch_err}")
                
        for m in movers_raw:
            sym = m.get('symbol')
            if not sym:
                continue
            sym = sym.upper()
            # Schwab netPercentChange is fractional (e.g. 0.6246 for 62.46%)
            change = round(m.get('netPercentChange', 0) * 100, 2)
            price = m.get('lastPrice') or 0
            volume = m.get('volume') or 0
            
            if sym not in candidate_data or abs(change) > abs(candidate_data[sym].get('change', 0)):
                candidate_data[sym] = {
                    'change': change,
                    'price': price,
                    'volume': volume,
                    'market_cap': None,
                    'float_shares': None,
                    'sector': None
                }
    except Exception as e:
        log.warning(f"[Schwab Client] Failed to merge Schwab movers: {e}")

    # 3. Fetch Watchlist Tickers from DB
    watchlist_tickers = set()
    try:
        from database import get_connection
        with get_connection() as conn:
            cur = conn.execute("SELECT ticker FROM watchlist")
            rows = cur.fetchall()
            for r in rows:
                ticker = r['ticker']
                if ticker:
                    watchlist_tickers.add(ticker.upper())
    except Exception as e:
        log.warning(f"[Schwab Client] Failed to fetch watchlist: {e}")

    # Ensure all watchlist tickers are in candidate_data (so we fetch their quotes)
    for sym in watchlist_tickers:
        if sym not in candidate_data:
            candidate_data[sym] = {
                'change': 0.0,
                'price': 0.0,
                'volume': 0.0,
                'market_cap': None,
                'float_shares': None,
                'sector': None
            }

    if not candidate_data:
        return []

    # 4. Construct top_candidates list:
    # Always include all watchlist tickers first.
    top_candidates = list(watchlist_tickers)
    
    # Sort non-watchlist candidates by absolute change descending
    non_watchlist_candidates = [sym for sym in candidate_data if sym not in watchlist_tickers]
    non_watchlist_candidates.sort(key=lambda x: abs(candidate_data[x].get('change', 0) or 0), reverse=True)
    
    # Fill remaining slots up to 150
    slots_left = max(0, 150 - len(top_candidates))
    top_candidates.extend(non_watchlist_candidates[:slots_left])

    # Batch fetch quotes in chunks of 50 (Schwab limit)
    all_quotes = {}
    for i in range(0, len(top_candidates), 50):
        chunk = top_candidates[i:i+50]
        try:
            quotes = get_quotes(chunk)
            all_quotes.update(quotes)
        except Exception as e:
            log.warning(f"[Schwab Client] Failed to get quotes for chunk {chunk}: {e}")

    tickers = []
    for sym, data in all_quotes.items():
        quote = data.get('quote', {})
        fund = data.get('fundamental', {})
        cdata = candidate_data.get(sym, {})
        
        ask = quote.get('askPrice')
        bid = quote.get('bidPrice')
        spread_pct = round(((ask - bid) / bid) * 100, 2) if ask and bid and bid > 0 else None
        
        last_price = quote.get('lastPrice')
        high_price = quote.get('highPrice')
        is_hod = (last_price >= (high_price * 0.995)) if last_price and high_price and high_price > 0 else False
        
        trade_time = quote.get('tradeTime')
        
        # Ensure we have a valid total volume, falling back to TradingView's volume if Schwab's is missing/0
        schwab_vol = quote.get('totalVolume')
        tv_vol = cdata.get('volume') or 0
        total_vol = schwab_vol if (schwab_vol is not None and schwab_vol > 0) else tv_vol
        
        avg_vol = fund.get('avg10DaysVolume') or fund.get('avg1YearVolume') or 0

        # Map to legacy MassiveSnapshotTicker shape
        tickers.append({
            'ticker': sym,
            'todaysChangePerc': quote.get('netPercentChange'),
            'lastTrade': {'p': quote.get('lastPrice')},
            'day': {
                'o': quote.get('openPrice'),
                'h': quote.get('highPrice'),
                'l': quote.get('lowPrice'),
                'c': quote.get('lastPrice'),
                'v': total_vol
            },
            'prevDay': {
                'c': quote.get('closePrice'),
                'v': avg_vol
            },
            'float_shares': cdata.get('float_shares'),
            'market_cap': cdata.get('market_cap'),
            'sector': cdata.get('sector'),
            'spread_pct': spread_pct,
            'ask': ask,
            'bid': bid,
            'trade_time': trade_time,
            'is_hod': is_hod
        })
    return tickers

def get_ticker_snapshot(ticker: str) -> Optional[Dict]:
    """Return a enriched snapshot dict compatible with legacy market routes."""
    try:
        res = get_quotes([ticker])
        if ticker in res:
            q = res[ticker].get('quote', {})
            return {
                'ticker': ticker,
                'last_trade': {'price': q.get('lastPrice')},
                'prev_day': {'close': q.get('closePrice')},
                'day': {
                    'v': q.get('totalVolume'),
                    'o': q.get('openPrice'),
                    'h': q.get('highPrice'),
                    'l': q.get('lowPrice'),
                    'c': q.get('lastPrice')
                }
            }
        return None
    except Exception as e:
        log.warning(f"[Schwab] get_ticker_snapshot({ticker}) failed: {e}")
        return None

def get_grouped_daily(date: str, adjusted: bool = True, include_otc: bool = False) -> Dict[str, Dict]:
    """
    Schwab does not support broad grouped daily snapshots. 
    Callers should migrate to per-ticker bars or use cached data.
    """
    log.debug(f"[Schwab] get_grouped_daily requested for {date} - NOT SUPPORTED")
    return {}

def get_minute_bars(ticker: str, start: str = None, end: str = None, limit: int = 50_000) -> List[Dict]:
    """
    Fetch minute bars and map to legacy MassiveAgg shape (o, h, l, c, v, vw, t).
    """
    try:
        # Schwab-py handles date ranges internally if start/end are provided
        candles = get_price_history_every_minute(ticker)
        return [
            {
                'o': c.get('open'),
                'h': c.get('high'),
                'l': c.get('low'),
                'c': c.get('close'),
                'v': c.get('volume'),
                't': c.get('datetime'),
                'vw': None # Schwab doesn't return bar-level VWAP in history
            } for c in candles
        ]
    except Exception as e:
        log.warning(f"[Schwab] get_minute_bars({ticker}) failed: {e}")
        return []

def get_daily_bars(ticker: str, start: str = None, end: str = None, limit: int = 5_000) -> List[Dict]:
    """
    Fetch daily bars and map to legacy MassiveAgg shape.
    """
    try:
        candles = get_price_history_every_day(ticker)
        return [
            {
                'o': c.get('open'),
                'h': c.get('high'),
                'l': c.get('low'),
                'c': c.get('close'),
                'v': c.get('volume'),
                't': c.get('datetime'),
                'vw': None
            } for c in candles
        ]
    except Exception as e:
        log.warning(f"[Schwab] get_daily_bars({ticker}) failed: {e}")
        return []

def get_last_trade(ticker: str) -> Optional[Dict]:
    try:
        res = get_quotes([ticker])
        if ticker in res:
            q = res[ticker].get('quote', {})
            return {'p': q.get('lastPrice'), 't': q.get('quoteTime')}
        return None
    except Exception as e:
        log.warning(f"[Schwab] get_last_trade({ticker}) failed: {e}")
        return None

def get_last_quote(ticker: str) -> Optional[Dict]:
    # Schwab quote includes bid/ask
    try:
        res = get_quotes([ticker])
        if ticker in res:
            q = res[ticker].get('quote', {})
            return {
                'p': q.get('lastPrice'),
                'as': q.get('askSize'),
                'ap': q.get('askPrice'),
                'bs': q.get('bidSize'),
                'bp': q.get('bidPrice'),
                't': q.get('quoteTime')
            }
        return None
    except Exception as e:
        log.warning(f"[Schwab] get_last_quote({ticker}) failed: {e}")
        return None

def get_latest_headline(ticker: str) -> Optional[str]:
    """News is not supported by Schwab Trader API."""
    return None

def get_ticker_details(ticker: str) -> Dict:
    """
    Fetch instrument details and map to legacy shape.
    """
    try:
        res = get_instruments([ticker])
        if ticker in res:
            inst = res[ticker]
            fund = inst.get('fundamental', {})
            return {
                "ticker":             ticker,
                "company_name":       inst.get('description'),
                "sector":             fund.get('sector'),
                "industry":           None,
                "description":        inst.get('description'),
                "market_cap":         fund.get('marketCap'),
                "float_shares":       None, # Schwab fundamentals are limited
                "shares_outstanding": fund.get('sharesOutstanding'),
                "exchange":           inst.get('exchange'),
                "_source":            "schwab",
            }
        return {}
    except Exception as e:
        log.warning(f"[Schwab] get_ticker_details({ticker}) failed: {e}")
        return {}
