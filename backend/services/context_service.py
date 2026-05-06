"""
context_service.py — Data gatherer for the Deep Context feature.

Aggregates signals from:
  - Polygon.io: 1Y daily OHLCV (for SMA/RS calculations)
  - yfinance: 52-week high/low, float, options chain, sector info
  - Our database: historical gainer appearances for this ticker
"""
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from config import Config
from database import get_connection

log = logging.getLogger(__name__)


def build_context_payload(ticker: str) -> dict:
    """
    Gather all signals needed for a Deep Context LLM report.

    Returns:
        Structured dict containing technical levels, float structure,
        relative strength, and historical gainer history from the journal.
    """
    payload = {
        'ticker':             ticker,
        'technical_levels':   _get_technical_levels(ticker),
        'price_range_52w':    _get_52w_range(ticker),
        'float_structure':    _get_float_structure(ticker),
        'relative_strength':  _get_relative_strength(ticker),
        'options_sentiment':  _get_options_sentiment(ticker),
        'journal_history':    _get_journal_history(ticker),
        'sector_context':     _get_sector_context(ticker),
    }
    return payload


# ---------------------------------------------------------------------------
# Individual signal collectors
# ---------------------------------------------------------------------------

def _get_daily_ohlcv(ticker: str, days: int = 252) -> pd.DataFrame:
    """
    Fetch daily OHLCV bars from Polygon (primary) or yfinance (fallback).
    Returns a DataFrame indexed by date with columns: open, high, low, close, volume.
    """
    # Try Polygon first
    if Config.POLYGON_API_KEY:
        try:
            end   = datetime.utcnow()
            start = end - timedelta(days=days + 30)
            url   = (
                f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day'
                f'/{start.strftime("%Y-%m-%d")}/{end.strftime("%Y-%m-%d")}'
            )
            params = {'adjusted': 'true', 'sort': 'asc', 'limit': 5000,
                      'apiKey': Config.POLYGON_API_KEY}
            resp = requests.get(url, params=params, timeout=12)
            resp.raise_for_status()
            results = resp.json().get('results', [])
            if results:
                df = pd.DataFrame(results)
                df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                        'c': 'close', 'v': 'volume', 't': 'ts'})
                df['date'] = pd.to_datetime(df['ts'], unit='ms').dt.strftime('%Y-%m-%d')
                df = df.set_index('date')
                return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            log.warning(f'[Context] Polygon daily fetch failed: {e}')

    # Fallback to yfinance
    try:
        import yfinance as yf
        end   = datetime.utcnow()
        start = end - timedelta(days=days + 30)
        df = yf.download(ticker, start=start.strftime('%Y-%m-%d'),
                         end=end.strftime('%Y-%m-%d'), interval='1d',
                         auto_adjust=True, progress=False)
        if df.empty:
            return pd.DataFrame()
        if hasattr(df.columns, 'levels'):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low',
                                 'Close': 'close', 'Volume': 'volume'})
        df.index = df.index.strftime('%Y-%m-%d')
        return df[['open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        log.warning(f'[Context] yfinance daily fallback failed: {e}')
        return pd.DataFrame()


def _get_technical_levels(ticker: str) -> dict:
    """
    Calculate key SMA levels and position relative to them.
    Returns SMA 20/50/200 values and whether price is above/below each.
    """
    try:
        df = _get_daily_ohlcv(ticker)
        if df.empty or len(df) < 20:
            return {}

        close = df['close']
        current_price = float(close.iloc[-1])

        levels = {'current_price': round(current_price, 4)}
        for period in [20, 50, 200]:
            if len(close) >= period:
                sma = float(close.rolling(period).mean().iloc[-1])
                levels[f'sma_{period}'] = round(sma, 4)
                levels[f'above_sma_{period}'] = current_price > sma
                levels[f'pct_from_sma_{period}'] = round(
                    (current_price - sma) / sma * 100, 2
                )

        # EMA 9, 21
        for span in [9, 21]:
            ema = float(close.ewm(span=span, adjust=False).mean().iloc[-1])
            levels[f'ema_{span}'] = round(ema, 4)

        # Recent trend: 5-day vs 20-day slope
        if len(close) >= 20:
            levels['trend_5d']  = round(float(close.iloc[-1] - close.iloc[-6]), 4)
            levels['trend_20d'] = round(float(close.iloc[-1] - close.iloc[-21]), 4)

        return levels
    except Exception as e:
        log.warning(f'[Context] Technical levels calc failed: {e}')
        return {}


def _get_52w_range(ticker: str) -> dict:
    """Return 52-week high, low, and current price position within that range."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        high = info.get('fiftyTwoWeekHigh')
        low  = info.get('fiftyTwoWeekLow')
        curr = info.get('currentPrice') or info.get('regularMarketPrice')

        result = {'high_52w': high, 'low_52w': low, 'current': curr}
        if high and low and curr and (high - low) > 0:
            result['position_in_range_pct'] = round(
                (curr - low) / (high - low) * 100, 1
            )
        return result
    except Exception as e:
        log.warning(f'[Context] 52-week range fetch failed: {e}')
        return {}


def _get_float_structure(ticker: str) -> dict:
    """Return float, shares outstanding, and float rotation estimate."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        float_shares = info.get('floatShares')
        shares_out   = info.get('sharesOutstanding')
        avg_vol      = info.get('averageVolume') or info.get('averageDailyVolume10Day')

        result = {
            'float_shares':       float_shares,
            'shares_outstanding': shares_out,
            'avg_daily_volume':   avg_vol,
        }
        if float_shares and avg_vol and float_shares > 0:
            result['float_rotation_days'] = round(float_shares / avg_vol, 1)
        if float_shares and shares_out and shares_out > 0:
            result['float_pct_of_outstanding'] = round(float_shares / shares_out * 100, 1)
        return result
    except Exception as e:
        log.warning(f'[Context] Float structure fetch failed: {e}')
        return {}


def _get_relative_strength(ticker: str, benchmark: str = 'SPY') -> dict:
    """
    Calculate a simple Relative Strength ratio vs SPY over 20 and 60 days.
    RS > 1 means the stock outperformed SPY over that period.
    """
    try:
        import yfinance as yf
        end   = datetime.utcnow()
        start = end - timedelta(days=90)

        data = yf.download(
            [ticker, benchmark],
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            interval='1d',
            auto_adjust=True,
            progress=False,
        )
        if data.empty:
            return {}

        closes = data['Close'] if 'Close' in data else data
        if ticker not in closes.columns or benchmark not in closes.columns:
            return {}

        t_close = closes[ticker].dropna()
        b_close = closes[benchmark].dropna()

        if len(t_close) < 20 or len(b_close) < 20:
            return {}

        rs_20 = round(float(t_close.iloc[-1] / t_close.iloc[-20]) /
                      float(b_close.iloc[-1] / b_close.iloc[-20]), 3)

        rs_60 = None
        if len(t_close) >= 60 and len(b_close) >= 60:
            rs_60 = round(float(t_close.iloc[-1] / t_close.iloc[-60]) /
                          float(b_close.iloc[-1] / b_close.iloc[-60]), 3)

        return {
            'vs_spy_20d': rs_20,
            'vs_spy_60d': rs_60,
            'outperforming_market_20d': rs_20 > 1.0,
        }
    except Exception as e:
        log.warning(f'[Context] Relative strength calc failed: {e}')
        return {}


def _get_options_sentiment(ticker: str) -> dict:
    """
    Fetch nearest-term options chain and compute put/call ratio.
    High P/C ratio (>1) signals fear; low P/C (<0.5) signals greed/squeeze potential.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        expiries = t.options
        if not expiries:
            return {'available': False}

        # Use next 2 expiry dates
        results = []
        for exp in expiries[:2]:
            chain = t.option_chain(exp)
            calls_vol = int(chain.calls['volume'].fillna(0).sum())
            puts_vol  = int(chain.puts['volume'].fillna(0).sum())
            pc_ratio  = round(puts_vol / calls_vol, 3) if calls_vol > 0 else None
            results.append({
                'expiry':           exp,
                'call_volume':      calls_vol,
                'put_volume':       puts_vol,
                'put_call_ratio':   pc_ratio,
                'sentiment':        (
                    'FEAR' if pc_ratio and pc_ratio > 1.2 else
                    'GREED' if pc_ratio and pc_ratio < 0.5 else
                    'NEUTRAL'
                ),
            })
        return {'chains': results}
    except Exception as e:
        log.warning(f'[Context] Options sentiment fetch failed: {e}')
        return {'available': False}


def _get_journal_history(ticker: str, limit: int = 20) -> list[dict]:
    """
    Pull the ticker's historical appearances in our own daily_gainers table.
    This gives the LLM real context about the stock's past behavior.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT date, gap_pct, float_shares, rvol_15m, sector,
                          news_headline, news_fresh, open_price, close_price
                   FROM daily_gainers
                   WHERE ticker = %s
                   ORDER BY date DESC
                   LIMIT %s""",
                (ticker.upper(), limit)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning(f'[Context] Journal history fetch failed: {e}')
        return []


def _get_sector_context(ticker: str) -> dict:
    """Return sector and industry for high-level context in the report."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return {
            'sector':   info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'beta':     info.get('beta'),
        }
    except Exception as e:
        log.warning(f'[Context] Sector context fetch failed: {e}')
        return {}
