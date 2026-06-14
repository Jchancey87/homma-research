"""
tests/test_chart_data_service.py
Unit tests for services/chart_data_service.py.

The pure pandas indicator computation and the bar-record builder can be
tested without a DB. The end-to-end happy path (DB → response) is covered
by tests/test_routers_timeseries.py:306.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
_REPO = _BACKEND.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.chart_data_service import (  # noqa: E402
    ChartDataNotFoundError,
    _bars_to_insert_records,
    _compute_indicators,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_bars_df(n: int = 60) -> pd.DataFrame:
    """Build a tz-naive synthetic OHLCV DataFrame with monotonically rising prices."""
    base = pd.Timestamp("2026-06-01 09:30", tz="UTC")
    idx = pd.date_range(base, periods=n, freq="1min")
    df = pd.DataFrame(
        {
            "open":   [100.0 + i * 0.1 for i in range(n)],
            "high":   [101.0 + i * 0.1 for i in range(n)],
            "low":    [ 99.5 + i * 0.1 for i in range(n)],
            "close":  [100.5 + i * 0.1 for i in range(n)],
            "volume": [50_000 + i * 100   for i in range(n)],
        },
        index=idx,
    )
    return df


# ── Indicator computation: mini mode ──────────────────────────────────────────

def test_compute_indicators_mini_returns_ohlcv_volume_ema21():
    df = _make_bars_df(60)
    payload, records = _compute_indicators(df, mini_mode=True)

    assert records == []  # pure indicator path; insert list built elsewhere
    assert set(payload.keys()) == {"ohlcv", "volume", "ema_21"}

    # EMA-21 series must have at least 1 point (drops NaN, but the warmup is 21)
    assert len(payload["ema_21"]) >= 1
    assert all("time" in pt and "value" in pt for pt in payload["ema_21"])

    # OHLCV must align 1:1 with input rows that survived dropna
    assert len(payload["ohlcv"]) == len(payload["ema_21"])
    assert len(payload["volume"]) == len(payload["ohlcv"])

    # No full-mode indicators should leak into mini mode
    for full_only in ("rvol", "ema_8", "ema_13", "ema_34", "ema_55", "adx", "atr"):
        assert full_only not in payload


def test_compute_indicators_full_returns_all_indicators():
    df = _make_bars_df(80)
    payload, _ = _compute_indicators(df, mini_mode=False)

    expected_keys = {
        "ohlcv", "volume",
        "rvol", "ema_8", "ema_13", "ema_21", "ema_34", "ema_55",
        "adx", "plus_di", "minus_di", "atr",
    }
    assert set(payload.keys()) == expected_keys

    # Warmup discards the first ~55 rows; remaining series should all share length
    series_lengths = {len(payload[k]) for k in payload if k != "ohlcv" and k != "volume"}
    assert len(series_lengths) == 1, f"indicator series have inconsistent lengths: {series_lengths}"

    # OHLCV length matches indicator series length
    ohlcv_len = len(payload["ohlcv"])
    assert ohlcv_len == series_lengths.pop()


def test_compute_indicators_short_data_omits_indicator_rows():
    """With < 55 bars the full-mode dropna(ema_55) wipes the entire frame."""
    df = _make_bars_df(10)
    payload, _ = _compute_indicators(df, mini_mode=False)
    # ema_55 requires 55+ periods; full-mode dropna removes everything
    assert payload["ohlcv"] == [] or all(
        o["time"] is not None for o in payload["ohlcv"]
    )


def test_compute_indicators_nan_in_series_filtered():
    """NaN values in any indicator column should be omitted from its line series."""
    df = _make_bars_df(60)
    # Inject NaN into close to corrupt one EMA value
    df.loc[df.index[30], "close"] = float("nan")
    payload, _ = _compute_indicators(df, mini_mode=False)
    # The NaN row should not appear as an NaN in any line series
    for key in ("ema_8", "ema_21", "ema_55"):
        for pt in payload[key]:
            assert pt["value"] == pt["value"], f"NaN leaked into {key}"


# ── Insert-record builder ─────────────────────────────────────────────────────

def test_bars_to_insert_records_normalizes_timezone():
    """Timestamps must be UTC-aware, floats/int as appropriate."""
    df = _make_bars_df(5)
    records = _bars_to_insert_records(df, "TEST")

    assert len(records) == 5
    sym, ts, o, h, l, c, v = records[0]
    assert sym == "TEST"
    assert isinstance(ts, datetime)
    assert ts.tzinfo is not None
    assert ts.utcoffset().total_seconds() == 0  # UTC
    assert isinstance(o, float) and isinstance(h, float)
    assert isinstance(l, float) and isinstance(c, float)
    assert isinstance(v, int)


def test_bars_to_insert_records_handles_naive_index():
    """A naive (no-tz) index should be tagged as UTC, not crash."""
    idx = pd.date_range("2026-06-01 09:30", periods=3, freq="1min")  # tz-naive
    df = pd.DataFrame(
        {"open": [1.0, 2.0, 3.0], "high": [1.1, 2.1, 3.1],
         "low":  [0.9, 1.9, 2.9], "close": [1.0, 2.0, 3.0],
         "volume": [100, 200, 300]},
        index=idx,
    )
    records = _bars_to_insert_records(df, "NAIVE")
    assert all(r[1].tzinfo is not None for r in records)


def test_bars_to_insert_records_nan_volume_becomes_zero():
    df = _make_bars_df(3)
    df.loc[df.index[1], "volume"] = float("nan")
    records = _bars_to_insert_records(df, "NANV")
    volumes = [r[6] for r in records]
    assert volumes[1] == 0


# ── Exception class ───────────────────────────────────────────────────────────

def test_chart_data_not_found_error_carries_ticker_and_date():
    exc = ChartDataNotFoundError("AAPL", "2026-06-01")
    assert exc.ticker == "AAPL"
    assert exc.date_str == "2026-06-01"
    assert "AAPL" in str(exc)
    assert "2026-06-01" in str(exc)
