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

def get_gainers_snapshot(include_otc: bool = False) -> List[Dict]:
    """
    Simulates Polygon's gainer snapshot using Schwab Movers + Bulk Quotes.
    """
    try:
        # Fetch movers from major exchanges
        movers_raw = []
        for exch in ['NASDAQ', 'NYSE']:
            movers_raw.extend(get_movers(exch))
        
        symbols = [m['symbol'] for m in movers_raw]
        if not symbols:
            return []
            
        # Enforce limit similar to Polygon
        symbols = symbols[:100]
        
        # Batch fetch quotes in chunks of 50 (Schwab limit)
        all_quotes = {}
        for i in range(0, len(symbols), 50):
            chunk = symbols[i:i+50]
            quotes = get_quotes(chunk)
            all_quotes.update(quotes)
        
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
    except Exception as e:
        log.warning(f"[Schwab] get_gainers_snapshot failed: {e}")
        return []

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
