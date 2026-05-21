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

def _get_tradingview_candidates() -> List[str]:
    """
    Fetches active/gaining tickers from TradingView.
    Looks at regular session gainers, pre-market gainers, and post-market gainers.
    """
    url = "https://scanner.tradingview.com/america/scan"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    candidates = set()
    
    # 1. Regular gainers
    payload_reg = {
        "filter": [
            {"left": "change", "operation": "greater", "right": 5},
            {"left": "volume", "operation": "greater", "right": 50000},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "sortBy": "change", "sortOrder": "desc"},
        "columns": ["name"],
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
        "symbols": {"query": {"types": []}, "sortBy": "premarket_change", "sortOrder": "desc"},
        "columns": ["name"],
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
        "symbols": {"query": {"types": []}, "sortBy": "postmarket_change", "sortOrder": "desc"},
        "columns": ["name"],
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
                    sym = r.get("d", [None])[0]
                    if sym and len(sym) <= 5:  # skip warrants/long weird symbols
                        candidates.add(sym.upper())
            else:
                log.warning(f"[TradingView] {label} failed: {resp.status_code}")
        except Exception as e:
            log.warning(f"[TradingView] {label} error: {e}")
            
    return sorted(list(candidates))

def get_gainers_snapshot(include_otc: bool = False) -> List[Dict]:
    """
    Simulates Polygon's gainer snapshot using a hybrid strategy:
    1. Try to fetch candidate tickers from TradingView (covering pre, regular, and post sessions).
    2. Fall back to Schwab's /movers endpoint if TradingView fails or returns nothing.
    3. Bulk fetch quotes from Schwab in chunks of 50.
    """
    candidates = []
    try:
        candidates = _get_tradingview_candidates()
    except Exception as e:
        log.warning(f"[Schwab Client] Failed to fetch candidates from TradingView: {e}")
        
    if not candidates:
        log.info("[Schwab Client] TradingView returned no candidates; falling back to Schwab Movers")
        try:
            # Fallback to Schwab Movers
            movers_raw = []
            for exch in ['NASDAQ', 'NYSE']:
                movers_raw.extend(get_movers(exch))
            candidates = [m['symbol'] for m in movers_raw]
        except Exception as e:
            log.warning(f"[Schwab Client] Schwab movers fallback failed: {e}")
            return []

    if not candidates:
        return []

    # Enforce limit similar to Polygon (e.g. 150 candidates to avoid making too many quote calls)
    candidates = candidates[:150]

    # Batch fetch quotes in chunks of 50 (Schwab limit)
    all_quotes = {}
    for i in range(0, len(candidates), 50):
        chunk = candidates[i:i+50]
        try:
            quotes = get_quotes(chunk)
            all_quotes.update(quotes)
        except Exception as e:
            log.warning(f"[Schwab Client] Failed to get quotes for chunk {chunk}: {e}")

    tickers = []
    for sym, data in all_quotes.items():
        quote = data.get('quote', {})
        fund = data.get('fundamental', {})
        
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
                'v': quote.get('totalVolume')
            },
            'prevDay': {
                'c': quote.get('closePrice'),
                'v': fund.get('avg10DaysVolume') # proxy for prevDay vol if needed
            }
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
