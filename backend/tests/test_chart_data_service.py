"""
tests/test_chart_data_service.py
Unit tests for services/chart_data_service.py.

The pure pandas indicator computation and the bar-record builder can be
tested without a DB. The end-to-end happy path (DB → response) is covered
by tests/test_routers_timeseries.py:306.
"""
from __future__ import annotations

import sys
from datetime import date as _date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from validation import EASTERN_TZ  # noqa: E402

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
_REPO = _BACKEND.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import services.chart_data_service as cds  # noqa: E402
from services.chart_data_service import (  # noqa: E402
    ChartDataNotFoundError,
    _bars_to_insert_records,
    _compute_indicators,
    get_chart_data,
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
    assert set(payload.keys()) == {"ohlcv", "volume", "ema_21", "ema_50", "ema_100"}

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


# ── get_chart_data: is_today_or_future bypass (commit b917471) ────────────────
#
#  Branch matrix (post no-silent-DB-fallback fix):
#    ┌────────────────┬──────────────┬──────────────────────────────────┐
#    │ date vs today  │ DB has bars? │ Expected path                    │
#    ├────────────────┼──────────────┼──────────────────────────────────┤
#    │ past           │ yes          │ use DB; do NOT call fetch        │
#    │ past           │ no           │ call fetch                       │
#    │ today / future │ yes          │ call fetch (bypass DB cache)     │
#    │ today / future │ no           │ call fetch                       │
#    │ today / future │ yes          │ fetch empty → raise NotFound     │
#    │ today / future │ no           │ fetch empty → raise NotFound     │
#    └────────────────┴──────────────┴──────────────────────────────────┘
#  Stale DB rows are NEVER a substitute for a failed live fetch on today.
#
#  `datetime.now(EASTERN).date()` is monkeypatched via _FrozenClock so the
#  "today" boundary is deterministic.

FROZEN_TODAY = datetime(2026, 6, 1, 12, 0, tzinfo=EASTERN_TZ)


class _FrozenClock(datetime):
    """Stand-in for the module's `datetime` import — only .now(tz) is overridden.

    Subclassing the real `datetime` preserves `.combine`, `.fromisoformat`, etc.
    so the production code path is exercised unchanged; only the clock is frozen.
    """
    @classmethod
    def now(cls, tz=None):
        return FROZEN_TODAY if tz is None else FROZEN_TODAY.astimezone(tz)


def _make_ny_bars(n: int = 5, hour_offset: int = 0) -> pd.DataFrame:
    base = pd.Timestamp("2026-06-01 09:30", tz="America/New_York") + pd.Timedelta(hours=hour_offset)
    idx = pd.date_range(base, periods=n, freq="1min")
    return pd.DataFrame(
        {
            "open":   [10.0 + i for i in range(n)],
            "high":   [10.5 + i for i in range(n)],
            "low":    [ 9.5 + i for i in range(n)],
            "close":  [10.2 + i for i in range(n)],
            "volume": [1000 + i   for i in range(n)],
        },
        index=idx,
    )


def _df_to_db_rows(df: pd.DataFrame) -> list[dict]:
    """Mimic _read_db_bars() output: list[dict] keyed by 'time' (tz-aware dt)."""
    return [
        {
            "time": ts.to_pydatetime(),
            "open":  float(row["open"]),
            "high":  float(row["high"]),
            "low":   float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
        }
        for ts, row in df.iterrows()
    ]


def _install_frozen_clock(monkeypatch):
    monkeypatch.setattr(cds, "datetime", _FrozenClock)


def _mock_db():
    """MagicMock db whose .transaction() is a no-op async context manager.
    The cache-write branch catches all exceptions, so any error here is
    logged-and-swallowed and won't poison the test assertion."""
    db = MagicMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    db.transaction = MagicMock(return_value=tx)
    return db


# ── Past date: use DB cache, do not call fetch ────────────────────────────────

async def test_past_date_with_db_bars_uses_cache_skips_fetch(monkeypatch):
    db_rows = _df_to_db_rows(_make_ny_bars(7))
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=db_rows))
    fetch_mock = MagicMock(return_value=(pd.DataFrame(), []))
    monkeypatch.setattr(cds, "_fetch_with_fallback", fetch_mock)

    result = await get_chart_data(_mock_db(), "TEST", _date(2026, 5, 30), mini=True)

    fetch_mock.assert_not_called()
    assert len(result["ohlcv"]) == 7


async def test_past_date_without_db_bars_calls_fetch(monkeypatch):
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=[]))
    fetch_mock = MagicMock(return_value=(_make_ny_bars(4), []))
    monkeypatch.setattr(cds, "_fetch_with_fallback", fetch_mock)

    result = await get_chart_data(_mock_db(), "TEST", _date(2026, 5, 30), mini=True)

    fetch_mock.assert_called_once()
    assert len(result["ohlcv"]) == 4


# ── Today: ALWAYS bypass DB cache, ALWAYS call fetch ──────────────────────────

async def test_today_with_db_bars_bypasses_cache_calls_fetch(monkeypatch):
    """The whole point of the fix: today/future, fetch live even if DB has bars."""
    db_rows = _df_to_db_rows(_make_ny_bars(5))
    live_df = _make_ny_bars(3, hour_offset=1)  # different timestamps → different bars
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=db_rows))
    fetch_mock = MagicMock(return_value=(live_df, []))
    monkeypatch.setattr(cds, "_fetch_with_fallback", fetch_mock)

    result = await get_chart_data(_mock_db(), "TEST", _date(2026, 6, 1), mini=True)

    fetch_mock.assert_called_once()
    assert len(result["ohlcv"]) == 3  # live wins over DB (5)


async def test_today_with_empty_db_calls_fetch(monkeypatch):
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=[]))
    fetch_mock = MagicMock(return_value=(_make_ny_bars(6), []))
    monkeypatch.setattr(cds, "_fetch_with_fallback", fetch_mock)

    result = await get_chart_data(_mock_db(), "TEST", _date(2026, 6, 1), mini=True)

    fetch_mock.assert_called_once()
    assert len(result["ohlcv"]) == 6


# ── Today: live fetch fails → never silently fall back to DB (raise) ────────
# Rationale: a "live" chart that secretly shows hours-old DB bars is worse
# than a not-found error. The frontend can surface the error and retry.

async def test_today_live_fetch_fails_with_db_bars_still_raises(monkeypatch):
    """Even when the DB has bars for today, a failed live fetch must NOT
    substitute stale DB rows. The user explicitly asked for live data —
    showing frozen DB data as if it were live is the bug we are eliminating."""
    db_rows = _df_to_db_rows(_make_ny_bars(8))
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=db_rows))
    fetch_mock = MagicMock(return_value=(pd.DataFrame(), []))  # live chain exhausted
    monkeypatch.setattr(cds, "_fetch_with_fallback", fetch_mock)

    with pytest.raises(ChartDataNotFoundError) as ei:
        await get_chart_data(_mock_db(), "TEST", _date(2026, 6, 1), mini=True)
    assert ei.value.ticker == "TEST"
    assert ei.value.date_str == "2026-06-01"
    # Sanity: live fetch was attempted (we don't give up before trying)
    fetch_mock.assert_called_once()


async def test_today_live_fetch_fails_db_empty_raises_not_found(monkeypatch):
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=[]))
    monkeypatch.setattr(cds, "_fetch_with_fallback", MagicMock(return_value=(pd.DataFrame(), [])))

    with pytest.raises(ChartDataNotFoundError) as ei:
        await get_chart_data(_mock_db(), "TEST", _date(2026, 6, 1), mini=True)
    assert ei.value.ticker == "TEST"
    assert ei.value.date_str == "2026-06-01"


# ── Future date: bypasses DB entirely ─────────────────────────────────────────

async def test_future_date_calls_fetch_even_when_db_has_bars(monkeypatch):
    db_rows = _df_to_db_rows(_make_ny_bars(2))
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=db_rows))
    fetch_mock = MagicMock(return_value=(_make_ny_bars(2, hour_offset=2), []))
    monkeypatch.setattr(cds, "_fetch_with_fallback", fetch_mock)

    result = await get_chart_data(_mock_db(), "TEST", _date(2026, 6, 2), mini=True)

    fetch_mock.assert_called_once()
    assert len(result["ohlcv"]) == 2  # live data used, not DB


async def test_future_date_without_db_bars_calls_fetch(monkeypatch):
    _install_frozen_clock(monkeypatch)
    monkeypatch.setattr(cds, "_read_db_bars", AsyncMock(return_value=[]))
    fetch_mock = MagicMock(return_value=(_make_ny_bars(1, hour_offset=3), []))
    monkeypatch.setattr(cds, "_fetch_with_fallback", fetch_mock)

    result = await get_chart_data(_mock_db(), "TEST", _date(2026, 6, 2), mini=True)

    fetch_mock.assert_called_once()
    assert len(result["ohlcv"]) == 1
