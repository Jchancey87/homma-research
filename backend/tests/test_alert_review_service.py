"""
tests/test_alert_review_service.py
Unit tests for services/alert_review_service.py
"""
from __future__ import annotations

from validation import EASTERN_TZ


def test_compute_mfe_mae_basic_favorable_move():
    trig_dt = EASTERN_TZ.localize(datetime(2026, 6, 1, 9, 30))
    trig_price = 10.0

    # Synthetic candles post-trigger
    # Min 0 (9:30): open=10.0, high=10.5, low=9.8, close=10.2
    # Min 5 (9:35): open=10.2, high=12.0, low=10.0, close=11.5
    # Min 15 (9:45): open=11.5, high=13.0, low=11.0, close=12.5
    # Min 30 (10:00): open=12.5, high=15.0, low=12.0, close=14.0
    candles = []
    for i in range(40):
        c_time = trig_dt + timedelta(minutes=i)
        # Price rises by 0.1 each minute, high is +0.5, low is -0.2
        price = 10.0 + i * 0.1
        candles.append({
            "time": c_time,
            "open": price,
            "high": price + 0.5,
            "low": price - 0.2,
            "close": price + 0.2,
        })

    res = compute_mfe_mae_for_candles(trig_price, trig_dt, candles)

    assert "5m" in res and "15m" in res and "30m" in res and "eod" in res

    # At 5m (up to 9:35, i=5, max high is 10.5 + 0.5 = 11.0)
    # mfe = (11.0 - 10.0) / 10.0 * 100 = 10.0%
    # min low is at i=0 (9.8), mae = (9.8 - 10.0) / 10.0 * 100 = -2.0%
    assert res["5m"]["mfe_pct"] == 10.0
    assert res["5m"]["mae_pct"] == -2.0

    # At 15m (up to 9:45, i=15, max high is 11.5 + 0.5 = 12.0)
    # mfe = (12.0 - 10.0) / 10.0 * 100 = 20.0%
    assert res["15m"]["mfe_pct"] == 20.0


def test_compute_mfe_mae_empty_candles():
    trig_dt = EASTERN_TZ.localize(datetime(2026, 6, 1, 9, 30))
    res = compute_mfe_mae_for_candles(10.0, trig_dt, [])
    assert res["15m"]["mfe_pct"] == 0.0
    assert res["15m"]["mae_pct"] == 0.0


def test_compute_mfe_mae_zero_trigger_price():
    trig_dt = EASTERN_TZ.localize(datetime(2026, 6, 1, 9, 30))
    candles = [{"time": trig_dt, "open": 10, "high": 11, "low": 9, "close": 10}]
    res = compute_mfe_mae_for_candles(0.0, trig_dt, candles)
    assert res["15m"]["mfe_pct"] == 0.0
