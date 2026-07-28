"""
Thread-Safe Screener Cache.

Encapsulates in-memory dictionary caches (_cache, _minute_cache, _daily_cache, _last_update_ts)
and locking discipline for fast (2s) Redis tick overlays and slow (60s) REST pipeline refreshes.
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


class ScreenerCache:
    """Thread-safe in-memory cache for live screener gainer table payloads."""

    def __init__(self):
        self._cache_lock = threading.RLock()
        self._minute_cache_lock = threading.Lock()
        self._daily_cache_lock = threading.Lock()

        self._cache: dict = {
            'gainers': [],
            'fetched_at': None,
            'session': 'UNKNOWN',
            'market_regime': 'UNKNOWN',
        }
        self._minute_cache: Dict[str, tuple] = {}   # ticker -> (ts, metrics_dict)
        self._daily_cache: Dict[str, tuple] = {}    # ticker -> (ts, data_dict)
        self._last_update_ts: Dict[str, float] = {} # ticker -> timestamp of last update

    def get_cache_snapshot(self) -> dict:
        with self._cache_lock:
            if self._cache['gainers']:
                return dict(self._cache)
            return {}


    def update_cache(self, gainers: List[dict], session: str = "REGULAR") -> dict:
        now = time.time()
        iso_now = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
        with self._cache_lock:
            self._cache['gainers'] = gainers
            self._cache['fetched_at'] = iso_now
            self._cache['session'] = session
            for g in gainers:
                t = g.get('ticker')
                if t:
                    self._last_update_ts[t] = now
            return dict(self._cache)

    def get_minute_cache(self, ticker: str, ttl_seconds: float = 30.0) -> Optional[dict]:
        now = time.time()
        with self._minute_cache_lock:
            if ticker in self._minute_cache:
                ts, cached = self._minute_cache[ticker]
                if now - ts < ttl_seconds:
                    return dict(cached)
        return None

    def store_minute_cache(self, ticker: str, metrics: dict) -> None:
        now = time.time()
        with self._minute_cache_lock:
            self._minute_cache[ticker] = (now, metrics)

    def get_daily_cache(self, ticker: str, ttl_seconds: float = 86400.0) -> Optional[dict]:
        now = time.time()
        with self._daily_cache_lock:
            if ticker in self._daily_cache:
                ts, cached = self._daily_cache[ticker]
                if now - ts < ttl_seconds:
                    return dict(cached)
        return None

    def store_daily_cache(self, ticker: str, data: dict) -> None:
        now = time.time()
        with self._daily_cache_lock:
            self._daily_cache[ticker] = (now, data)

    def overlay_streaming_ticks(self, streamed_prices: dict) -> Tuple[bool, int]:
        """
        Overlay real-time WebSocket Redis price ticks on cached gainers.
        Returns (fast_mode_active: bool, streaming_symbols_count: int).
        """
        with self._cache_lock:
            gainers = self._cache.get('gainers')
            if not gainers or not streamed_prices:
                return False, len(streamed_prices)

            now = time.time()
            updated_count = 0

            for g in gainers:
                ticker = g.get('ticker')
                if not ticker or ticker not in streamed_prices:
                    continue

                snap = streamed_prices[ticker]
                last_update = self._last_update_ts.get(ticker, 0)
                if snap.timestamp < last_update:
                    continue

                g['last_price'] = snap.last_price
                if snap.high_price > 0:
                    g['high_price'] = snap.high_price
                if snap.low_price > 0:
                    g['low_price'] = snap.low_price

                # Recalculate gap % if prev_close exists
                prev_close = g.get('prev_close')
                if prev_close and prev_close > 0:
                    g['gap_pct'] = round(((snap.last_price - prev_close) / prev_close) * 100, 2)

                self._last_update_ts[ticker] = snap.timestamp
                updated_count += 1

            iso_now = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
            self._cache['fetched_at'] = iso_now
            return updated_count > 0, len(streamed_prices)
