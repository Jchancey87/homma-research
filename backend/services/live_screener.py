"""
Live Gainer Screener Orchestrator.

Thin orchestrator wiring candidate sourcing, metrics, and thread-safe cache.
"""

import threading
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict

from validation import EASTERN_TZ
from services.screener_metrics import calculate_ema, calculate_atr, calculate_vwap, build_sparkline, calculate_ross_metrics
from services.screener_cache import ScreenerCache
from services.screener_source import ScreenerCandidateSource

log = logging.getLogger(__name__)

# Constants
EASTERN = EASTERN_TZ
CACHE_TTL_SECONDS = 3
FAST_REFRESH_SECONDS = 2
SLOW_REFRESH_SECONDS = 60
MIN_GAP_PCT = 10.0
MIN_PRICE = 1.00
MAX_PRICE = 20.00
TOP_N = 25

# Global ScreenerCache instance
screener_cache = ScreenerCache()
candidate_source = ScreenerCandidateSource()


def get_market_session(now_et: Optional[datetime] = None) -> str:
    if now_et is None:
        now_et = datetime.now(EASTERN)
    if now_et.weekday() >= 5:
        return 'closed'
    hm = now_et.hour * 60 + now_et.minute
    if 4 * 60 <= hm < 9 * 60 + 30:
        return 'pre_market'
    elif 9 * 60 + 30 <= hm < 16 * 60:
        return 'open'
    elif 16 * 60 <= hm < 20 * 60:
        return 'after_hours'
    else:
        return 'closed'


def get_session_label(session: str) -> str:
    return {
        'pre_market': '🌅 Pre-Market',
        'open': '🟢 Market Open',
        'after_hours': '🌙 After-Hours',
        'closed': '⏸ Market Closed',
    }.get(session, session)


def _compute_minute_metrics(ticker: str, last_price: Optional[float],
                             high_price: Optional[float],
                             bid: Optional[float], ask: Optional[float]) -> dict:
    """Fetch intraday minute metrics using ScreenerCache."""
    cached = screener_cache.get_minute_cache(ticker, ttl_seconds=120.0)
    if cached is not None:
        if last_price is not None:
            if cached.get('intraday_sparkline') and len(cached['intraday_sparkline']) > 0:
                cached['intraday_sparkline'][-1] = last_price
            if cached.get('sparkline_1h') and len(cached['sparkline_1h']) > 0:
                cached['sparkline_1h'][-1] = last_price
        return cached

    intraday_sparkline: List[float] = []
    sparkline_1h: List[float] = []

    try:
        from services.schwab_client import get_price_history_every_minute
        bars = get_price_history_every_minute(ticker)
        if bars:
            closes = [float(b['close']) for b in bars if b.get('close') is not None]
            if closes:
                intraday_sparkline = build_sparkline(closes, max_points=30)
                sparkline_1h = build_sparkline(closes[-60:], max_points=30)
    except Exception as e:
        log.debug(f"[Screener] Sparkline candle fetch failed for {ticker}: {e}")

    if not intraday_sparkline and last_price is not None:
        intraday_sparkline = [last_price]
    if not sparkline_1h and last_price is not None:
        sparkline_1h = [last_price]

    metrics = {
        'mom_2m': None,
        'vwap': last_price,
        'atr_14': None,
        'atr_hod': None,
        'atr_sprd': None,
        'atr_vwap': None,
        'zen_v': None,
        'intraday_sparkline': intraday_sparkline,
        'sparkline_1h': sparkline_1h,
        'hod': high_price or last_price,
    }
    screener_cache.store_minute_cache(ticker, metrics)
    return metrics


def _enrich_fundamentals(tickers: List[str]) -> Dict[str, dict]:
    """Batch fetch fundamentals from database for candidate symbols."""
    if not tickers:
        return {}
    results = {}
    try:
        from database import get_connection
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT symbol, company_name, shares_outstanding, market_cap
                FROM stock_fundamentals
                WHERE symbol = ANY(%s)
            """, (tickers,))
            for r in cur.fetchall():
                results[r['symbol']] = {
                    'company_name': r.get('company_name'),
                    'float_shares': r.get('shares_outstanding'),
                    'market_cap': r.get('market_cap'),
                }
            cur.execute("""
                SELECT DISTINCT ON (ticker) ticker, float_shares, sector, market_cap
                FROM daily_gainers
                WHERE ticker = ANY(%s)
                ORDER BY ticker, date DESC
            """, (tickers,))
            for r in cur.fetchall():
                sym = r['ticker']
                if sym not in results:
                    results[sym] = {}
                if r.get('float_shares'):
                    results[sym]['float_shares'] = r.get('float_shares')
                if r.get('sector'):
                    results[sym]['sector'] = r.get('sector')
                if r.get('market_cap'):
                    results[sym]['market_cap'] = r.get('market_cap')
    except Exception as e:
        log.warning(f"[Screener] Fundamentals enrichment DB lookup failed: {e}")
    return results


def refresh_cache(force: bool = False) -> dict:
    """Full pipeline refresh: candidate sourcing -> quotes -> metrics -> cache update."""
    existing = screener_cache.get_cache_snapshot()
    if existing and not force:
        return existing

    session = get_market_session()

    try:
        raw_candidates = candidate_source.fetch_candidates(limit=150)
        candidate_syms = [c.get('symbol') for c in raw_candidates if c.get('symbol')]
        fundamentals = _enrich_fundamentals(candidate_syms)

        gainers = []
        for c in raw_candidates:
            sym = c.get('symbol')
            if not sym:
                continue

            last_p = c.get('last_price') or c.get('lastPrice') or c.get('price') or c.get('last')
            if last_p is None:
                continue
            last_p = float(last_p)

            gap = None
            if c.get('gap_pct') is not None:
                gap = float(c['gap_pct'])
            elif c.get('netPercentChange') is not None:
                val = float(c['netPercentChange'])
                gap = val * 100.0 if abs(val) < 5.0 else val
            elif c.get('change') is not None:
                val = float(c['change'])
                gap = val * 100.0 if abs(val) < 5.0 else val
            elif c.get('netChange') is not None and last_p > 0:
                nc = float(c['netChange'])
                prev = last_p - nc
                if prev > 0:
                    gap = (nc / prev) * 100.0

            if gap is None:
                continue
            gap = float(gap)

            if last_p < MIN_PRICE or last_p > MAX_PRICE or gap < MIN_GAP_PCT:
                continue

            volume = int(c.get('totalVolume') or c.get('volume') or 100000)

            if c.get('netChange') is not None:
                prev_close = last_p - float(c['netChange'])
            else:
                prev_close = last_p / (1 + gap / 100) if (1 + gap / 100) > 0 else last_p

            fund = fundamentals.get(sym, {})
            co_name = fund.get('company_name') or c.get('description') or c.get('company_name') or sym
            fl_shares = fund.get('float_shares') or c.get('float_shares')
            mkt_cap = fund.get('market_cap') or c.get('market_cap')
            sec = fund.get('sector') or c.get('sector') or 'Unknown'

            gainers.append({
                'ticker': sym,
                'company_name': co_name,
                'gap_pct': round(gap, 2),
                'last_price': round(last_p, 2),
                'high_price': round(last_p, 2),
                'low_price': round(last_p, 2),
                'open_price': round(last_p, 2),
                'prev_close': round(prev_close, 2),
                'volume': volume,
                'rvol_15m': round(float(c.get('rvol_15m', 2.5)), 2),
                'float_shares': fl_shares,
                'market_cap': mkt_cap,
                'sector': sec,
                'ask': round(last_p + 0.01, 2),
                'bid': round(last_p - 0.01, 2),
                'spread_pct': 0.2,
                'is_hod': True,
                'in_watchlist': False,
                'news_headline': c.get('news_headline'),
                'news_fresh': c.get('news_fresh'),
            })

        gainers.sort(key=lambda x: -x['gap_pct'])
        top_gainers = gainers[:TOP_N]

        # Batch compute minute metrics & sparklines ONLY for the final top gainers in parallel
        from concurrent.futures import ThreadPoolExecutor
        def _fetch_metrics(g):
            mm = _compute_minute_metrics(g['ticker'], g['last_price'], g['high_price'], None, None)
            g['sparkline_intraday'] = mm.get('intraday_sparkline', [])
            g['sparkline_1h'] = mm.get('sparkline_1h', [])

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(_fetch_metrics, top_gainers))

        return screener_cache.update_cache(top_gainers, session=session)

    except Exception as e:
        log.error(f"[Screener] refresh_cache failed: {e}")
        return screener_cache.get_cache_snapshot()


def get_live_gainers(force: bool = False) -> dict:
    """Public API for live gainers endpoint."""
    res = refresh_cache(force=force)

    try:
        from services.streaming_prices import get_bridge
        bridge = get_bridge()
        streamed = bridge.get_all_prices()
        fast_mode, symbol_count = screener_cache.overlay_streaming_ticks(streamed)
        res['fast_mode_active'] = fast_mode
        res['streaming_symbols_count'] = symbol_count
        res['redis_connected'] = True
    except Exception as e:
        log.debug(f"[Screener] streaming price overlay skipped: {e}")
        res['fast_mode_active'] = False
        res['streaming_symbols_count'] = 0
        res['redis_connected'] = False

    return res
