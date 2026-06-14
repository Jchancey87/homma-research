"""
tests/test_alerts_analytics.py
Unit tests for services/alerts_analytics.py.

The pure transforms (_forward_returns_from_candles, _group_alerts_by_ticker,
_scorecard_row) can be tested without a DB. The async I/O paths are covered
by tests/test_alerts.py integration tests.

Production code uses asyncpg.Record which supports `r['col']` and `r.col`;
fixtures here use plain dicts to mirror that subscript contract.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
_REPO = _BACKEND.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.alerts_analytics import (  # noqa: E402
    _forward_returns_from_candles,
    _group_alerts_by_ticker,
    _scorecard_row,
)


# ── Forward returns from candles ─────────────────────────────────────────────

def _candle(close: float, high: float = None, low: float = None) -> dict:
    return {
        "close": close,
        "high": close if high is None else high,
        "low": close if low is None else low,
    }


def test_forward_returns_empty_candles_returns_empty_dict():
    assert _forward_returns_from_candles(10.0, []) == {}


def test_forward_returns_zero_trigger_returns_empty_dict():
    candles = [_candle(10.5), _candle(11.0)]
    assert _forward_returns_from_candles(0, candles) == {}


def test_forward_returns_negative_trigger_returns_empty_dict():
    candles = [_candle(10.5)]
    assert _forward_returns_from_candles(-5.0, candles) == {}


def test_forward_returns_first_minute_sets_fwd_1m():
    candles = [_candle(11.0)]  # 1 candle = minute 1
    result = _forward_returns_from_candles(10.0, candles)
    assert result["fwd_1m"] == 10.0  # (11-10)/10 * 100


def test_forward_returns_three_minute_marks():
    candles = [_candle(c) for c in [10.0, 10.0, 11.0]]  # minute 1, 2, 3
    result = _forward_returns_from_candles(10.0, candles)
    assert result["fwd_1m"] == 0.0
    assert result["fwd_3m"] == 10.0


def test_forward_returns_five_and_fifteen_minute_marks():
    closes = [10.0] * 5 + [12.0] + [10.0] * 8 + [12.0]  # 15 bars; bar 6 and bar 15 = 12.0
    candles = [_candle(c) for c in closes]
    result = _forward_returns_from_candles(10.0, candles)
    assert result["fwd_5m"] == 0.0    # bar 5 (i=4) close = 10.0
    assert result["fwd_15m"] == 20.0  # bar 15 (i=14) close = 12.0


def test_forward_returns_mfe_uses_max_high():
    """MFE = (max high - trigger) / trigger * 100, not based on closes alone."""
    candles = [
        _candle(close=10.0, high=10.5, low=9.8),
        _candle(close=11.0, high=11.5, low=10.7),
        _candle(close=10.5, high=10.6, low=9.5),
    ]
    result = _forward_returns_from_candles(10.0, candles)
    assert result["mfe"] == 15.0
    assert result["mae"] == -5.0


def test_forward_returns_values_rounded_to_2dp():
    candles = [_candle(10.123456)]
    result = _forward_returns_from_candles(10.0, candles)
    assert result["fwd_1m"] == 1.23


# ── Ticker grouping ───────────────────────────────────────────────────────────

def _row(alert_id: int, symbol: str, alert_time, alert_type="HOD",
         rel_vol=2.0, gap_pct=10.0, company_name=None, **extra) -> dict:
    base = {
        "id": alert_id,
        "symbol": symbol,
        "alert_time": alert_time,
        "trigger_price": 10.0,
        "trigger_volume": 1000,
        "rel_vol": rel_vol,
        "gap_pct": gap_pct,
        "float_shares": 1_000_000,
        "alert_type": alert_type,
        "sent": True,
        "feedback_score": None,
        "feedback_notes": None,
        "company_name": company_name,
        "float_category": "Micro",
        "market_cap": 50_000_000,
    }
    base.update(extra)
    return base


def test_group_empty_rows_returns_empty_list():
    assert _group_alerts_by_ticker([], {}) == []


def test_group_single_alert_creates_one_ticker_with_one_alert():
    now = datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)
    rows = [_row(1, "AAPL", now, company_name="Apple Inc")]
    out = _group_alerts_by_ticker(rows, {1: {"fwd_5m": 1.5, "mfe": 2.0}})

    assert len(out) == 1
    g = out[0]
    assert g["symbol"] == "AAPL"
    assert g["company_name"] == "Apple Inc"
    assert g["float_category"] == "Micro"
    assert g["gap_pct"] == 10.0
    assert g["rvol"] == 2.0
    assert len(g["alerts"]) == 1
    a = g["alerts"][0]
    assert a["id"] == 1
    assert a["alert_type"] == "HOD"
    assert a["fwd_5m"] == 1.5
    assert a["mfe"] == 2.0
    # Forward-returns keys not in the fwd dict should be None
    assert a["fwd_1m"] is None
    assert a["fwd_3m"] is None
    assert a["fwd_15m"] is None
    assert a["mae"] is None


def test_group_multiple_alerts_same_symbol_group_under_one_ticker():
    t1 = datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 14, 10, 15, tzinfo=timezone.utc)
    rows = [
        _row(1, "AAPL", t1, alert_type="HOD_BREAKOUT"),
        _row(2, "AAPL", t2, alert_type="VWAP_CROSSOVER"),
    ]
    out = _group_alerts_by_ticker(rows, {1: {}, 2: {}})
    assert len(out) == 1
    assert len(out[0]["alerts"]) == 2
    assert out[0]["alerts"][0]["id"] == 1
    assert out[0]["alerts"][1]["id"] == 2


def test_group_multiple_symbols_preserve_first_seen_order():
    t = datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)
    rows = [
        _row(1, "AAPL", t, company_name="Apple"),
        _row(2, "MSFT", t, company_name="Microsoft"),
        _row(3, "AAPL", t, alert_type="HOD_BREAKOUT"),
        _row(4, "NVDA", t, company_name="Nvidia"),
    ]
    out = _group_alerts_by_ticker(rows, {1: {}, 2: {}, 3: {}, 4: {}})
    assert [g["symbol"] for g in out] == ["AAPL", "MSFT", "NVDA"]
    assert len(out[0]["alerts"]) == 2


def test_group_alert_time_serialized_to_iso():
    t = datetime(2026, 6, 14, 10, 0, 0, tzinfo=timezone.utc)
    rows = [_row(1, "AAPL", t)]
    out = _group_alerts_by_ticker(rows, {1: {}})
    assert out[0]["alerts"][0]["alert_time"] == "2026-06-14T10:00:00+00:00"


def test_group_missing_fwd_dict_returns_alert_without_forward_fields():
    t = datetime(2026, 6, 14, 10, 0, tzinfo=timezone.utc)
    rows = [_row(1, "AAPL", t)]
    out = _group_alerts_by_ticker(rows, {})
    a = out[0]["alerts"][0]
    assert a["fwd_1m"] is None and a["fwd_15m"] is None
    assert a["mfe"] is None and a["mae"] is None


# ── Scorecard row mapping ─────────────────────────────────────────────────────

def test_scorecard_row_includes_all_fields():
    r = {
        "alert_type": "HOD_BREAKOUT",
        "price_bucket": "$2-5",
        "float_category": "Micro",
        "sample_count": 42,
        "avg_fwd_5m": 1.23,
        "avg_fwd_15m": 2.34,
        "win_rate_5m_pct": 58.5,
        "avg_mfe_pct": 4.56,
        "avg_mae_pct": -1.23,
    }
    out = _scorecard_row(r)
    assert out == {
        "alert_type": "HOD_BREAKOUT",
        "price_bucket": "$2-5",
        "float_category": "Micro",
        "sample_count": 42,
        "avg_fwd_5m": 1.23,
        "avg_fwd_15m": 2.34,
        "win_rate_5m_pct": 58.5,
        "avg_mfe_pct": 4.56,
        "avg_mae_pct": -1.23,
    }


def test_scorecard_row_handles_null_aggregates():
    r = {
        "alert_type": "UNKNOWN",
        "price_bucket": "$15+",
        "float_category": None,
        "sample_count": 0,
        "avg_fwd_5m": None,
        "avg_fwd_15m": None,
        "win_rate_5m_pct": None,
        "avg_mfe_pct": None,
        "avg_mae_pct": None,
    }
    out = _scorecard_row(r)
    assert out["avg_fwd_5m"] is None
    assert out["win_rate_5m_pct"] is None
    assert out["float_category"] is None
    assert out["sample_count"] == 0
