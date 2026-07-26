"""
Unit tests for pure Alert Detection Service.
Tests alert evaluation logic without DB, Redis, or network dependencies.
"""

import time
from datetime import datetime
import pytest
from validation import EASTERN_TZ
from backend.services.alert_detection_service import (
    QuoteTick,
    SymbolState,
    AlertConfig,
    evaluate_alerts,
    get_cumulative_volume_fraction,
    volume_spike_threshold,
)


def test_cumulative_volume_fraction_bounds():
    """Verify intraday volume fraction U-curve is bounded between 0.05 and 1.0."""
    frac_morning = get_cumulative_volume_fraction()
    assert 0.05 <= frac_morning <= 1.0


def test_prev_day_breakout_trigger():
    """Verify PREV_DAY_BREAKOUT fires when price breaches yesterday's high."""
    tick = QuoteTick(
        symbol="AAPL",
        last_price=155.0,
        total_volume=500000,
        high_price=155.5,
        low_price=149.0,
        open_price=151.0
    )
    state = SymbolState(symbol="AAPL")
    fund = {"yesterday_high": 150.0, "yesterday_close": 148.0, "vol_10d_avg": 1000000}

    candidates, updated_state = evaluate_alerts(tick, state, fund)

    assert any(c.alert_type == "PREV_DAY_BREAKOUT" for c in candidates)
    assert updated_state.prev_day_breakout_fired is True

    # Second tick above high should NOT refire PREV_DAY_BREAKOUT
    tick2 = QuoteTick(symbol="AAPL", last_price=156.0, total_volume=510000)
    candidates2, _ = evaluate_alerts(tick2, updated_state, fund)
    assert not any(c.alert_type == "PREV_DAY_BREAKOUT" for c in candidates2)


def test_vwap_crossover_hysteresis():
    """Verify VWAP_CROSSOVER requires state transition from 'below' to 'above'."""
    tick_below = QuoteTick(symbol="TSLA", last_price=95.0, total_volume=1000000)
    state = SymbolState(
        symbol="TSLA",
        vwap_state={"cum_vp": 100000000.0, "cum_vol": 1000000, "last_total_vol": 1000000, "status": "below"}
    )
    fund = {"yesterday_close": 98.0, "vol_10d_avg": 2000000}

    # Tick at VWAP (100.0) with rvol high enough
    now_et = EASTERN_TZ.localize(datetime(2026, 6, 1, 9, 35))
    tick_cross = QuoteTick(symbol="TSLA", last_price=105.0, total_volume=2000000)
    candidates, updated_state = evaluate_alerts(tick_cross, state, fund, now_et=now_et)

    assert updated_state.vwap_state["status"] == "above"
    assert any(c.alert_type == "VWAP_CROSSOVER" for c in candidates)


def test_post_halt_suppression():
    """Verify momentum alerts are suppressed during 2-minute post-halt window."""
    now_ts = time.time()
    tick = QuoteTick(symbol="GME", last_price=25.0, total_volume=300000)
    state = SymbolState(symbol="GME", halt_resume_ts=now_ts - 30)  # Resumed 30s ago
    fund = {"yesterday_high": 20.0, "yesterday_close": 18.0, "vol_10d_avg": 500000}

    candidates, _ = evaluate_alerts(tick, state, fund)

    # PREV_DAY_BREAKOUT is allowed, but post-halt suppressed triggers are skipped
    vwap_triggers = [c for c in candidates if c.alert_type == "VWAP_CROSSOVER"]
    assert len(vwap_triggers) == 0
