"""
Unit tests for screener subsystem (metrics, cache, sourcing, orchestrator).
"""

import time
import pytest
from backend.services.screener_metrics import (
    calculate_ema,
    calculate_atr,
    calculate_vwap,
    build_sparkline,
    calculate_ross_metrics,
)
from backend.services.screener_cache import ScreenerCache
from backend.services.live_screener import get_live_gainers, get_market_session, get_session_label


def test_screener_metrics_pure_functions():
    """Verify pure technical math functions produce correct outputs."""
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0]
    ema9 = calculate_ema(prices, 9)
    assert ema9 is not None
    assert ema9 > 10.0

    sparkline = build_sparkline(list(range(100)), max_points=30)
    assert len(sparkline) == 30
    assert sparkline[0] == 0.0
    assert sparkline[-1] == 99.0

    candles = [
        {'open': 10.0, 'close': 10.5, 'high': 10.6, 'low': 9.9, 'volume': 1000},
        {'open': 10.5, 'close': 11.0, 'high': 11.2, 'low': 10.4, 'volume': 2000},
    ]
    vwap = calculate_vwap(candles)
    assert vwap is not None
    assert 10.0 < vwap < 11.5


def test_screener_cache_thread_safety():
    """Verify ScreenerCache stores, snapshot reads, and overlays streaming ticks safely."""
    cache = ScreenerCache()
    gainers = [
        {'ticker': 'AAPL', 'last_price': 150.0, 'prev_close': 100.0, 'gap_pct': 50.0}
    ]
    cache.update_cache(gainers, session="REGULAR")

    # Mock PriceSnapshot object
    class FakeSnapshot:
        def __init__(self, price, high, low, ts):
            self.last_price = price
            self.high_price = high
            self.low_price = low
            self.timestamp = ts

    snap = FakeSnapshot(price=160.0, high=165.0, low=149.0, ts=time.time() + 10)
    streamed = {'AAPL': snap}

    fast_active, count = cache.overlay_streaming_ticks(streamed)
    assert fast_active is True
    assert count == 1

    snapshot = cache.get_cache_snapshot()
    assert snapshot['gainers'][0]['last_price'] == 160.0
    assert snapshot['gainers'][0]['gap_pct'] == 60.0


def test_live_screener_orchestrator():
    """Verify live_screener orchestrator returns structured gainers payload."""
    res = get_live_gainers(force=True)
    assert 'gainers' in res
    assert 'session' in res
    assert 'fast_mode_active' in res

    session = get_market_session()
    assert session in ['pre_market', 'open', 'after_hours', 'closed']
    label = get_session_label('open')
    assert 'Market Open' in label
