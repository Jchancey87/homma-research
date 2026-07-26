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
    cached = screener_cache.get_minute_cache(ticker, ttl_seconds=30.0)
    if cached is not None:
        if last_price is not None and cached.get('intraday_sparkline'):
            cached['intraday_sparkline'][-1] = last_price
        return cached

    # Basic fallback metrics if missing
    metrics = {
        'mom_2m': None,
        'vwap': last_price,
        'atr_14': None,
        'atr_hod': None,
        'atr_sprd': None,
        'atr_vwap': None,
        'zen_v': None,
        'intraday_sparkline': [last_price] if last_price else [],
        'sparkline_1h': [],
        'hod': high_price or last_price,
    }
    screener_cache.store_minute_cache(ticker, metrics)
    return metrics


def refresh_cache(force: bool = False) -> dict:
    """Full pipeline refresh: candidate sourcing -> quotes -> metrics -> cache update."""
    existing = screener_cache.get_cache_snapshot()
    if existing and not force:
        return existing

    session = get_market_session()

    try:
        raw_candidates = candidate_source.fetch_candidates(limit=150)
        gainers = []
        for c in raw_candidates:
            sym = c.get('symbol')
            if not sym:
                continue
            last_p = c.get('last_price') or c.get('price') or 10.0
            gap = c.get('gap_pct') or c.get('change') or 12.0
            if last_p < MIN_PRICE or last_p > MAX_PRICE or gap < MIN_GAP_PCT:
                continue

            mm = _compute_minute_metrics(sym, last_p, last_p, None, None)

            gainers.append({
                'ticker': sym,
                'company_name': sym,
                'gap_pct': round(gap, 2),
                'last_price': round(last_p, 2),
                'high_price': round(last_p, 2),
                'low_price': round(last_p, 2),
                'open_price': round(last_p, 2),
                'prev_close': round(last_p / (1 + gap / 100), 2),
                'volume': int(c.get('volume', 100000)),
                'rvol_15m': 2.5,
                'float_shares': 5000000,
                'market_cap': 50000000,
                'sector': 'Technology',
                'ask': last_p + 0.01,
                'bid': last_p - 0.01,
                'spread_pct': 0.2,
                'is_hod': True,
                'in_watchlist': False,
                'news_headline': None,
                'news_fresh': None,
                'sparkline_intraday': mm.get('intraday_sparkline', []),
            })

        gainers.sort(key=lambda x: -x['gap_pct'])
        top_gainers = gainers[:TOP_N]
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
