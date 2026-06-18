"""
services/chart_data_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deep module that owns the OHLCV → chart-payload pipeline.

Public surface (single function):

    get_chart_data(db, ticker, date, mini=False) -> dict

The router layer calls only this. All pandas math, fallback fetching,
and DB cache writes live here so they can be unit-tested without an
HTTP layer.

Originally extracted from routers/analysis.py:301-528 (RFC-001).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date as _date, datetime, time, timedelta
from typing import Optional

import asyncpg
import numpy as np
import pandas as pd
import pytz

from validation import EASTERN_TZ, normalize_ticker

log = logging.getLogger(__name__)

EASTERN = EASTERN_TZ  # canonical "America/New_York" tz; legacy alias kept for in-file use
UTC = pytz.utc
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


class ChartDataNotFoundError(Exception):
    """Raised when no intraday data can be located for the requested ticker+date."""

    def __init__(self, ticker: str, date_str: str):
        self.ticker = ticker
        self.date_str = date_str
        super().__init__(f"No intraday data available for {ticker} on {date_str}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_chart_data(
    db: asyncpg.Connection,
    ticker: str,
    date: _date,
    mini: bool = False,
) -> dict:
    """
    Return OHLCV + indicator series as a JSON-ready dict for the Lightweight
    Charts frontend.

    Pipeline:
      1. Try TimescaleDB (price_history_1min).
      2. Fall back to Schwab → Polygon → yfinance → prev-day Polygon → prev-day yfinance.
      3. Compute indicators (EMA / RVOL / ADX / +DI / -DI / ATR; EMA-21 only in mini mode).
      4. If bars came from an external source, cache them in price_history_1min.

    Raises:
        ChartDataNotFoundError: when the entire fallback chain returns no data.
    """
    ticker_val = normalize_ticker(ticker)
    date_str = date.isoformat()
    start_dt = EASTERN.localize(datetime.combine(date, time.min))
    end_dt = EASTERN.localize(datetime.combine(date, time.max))

    today_ny = datetime.now(EASTERN).date()
    is_today_or_future = (date >= today_ny)

    db_bars = await _read_db_bars(db, ticker_val, start_dt, end_dt)

    bars_df = pd.DataFrame()
    records_to_insert: list[tuple] = []

    if is_today_or_future:
        # For today/future, always try fetching live data to get newly formed bars
        bars_df, records_to_insert = await asyncio.to_thread(
            _fetch_with_fallback, ticker_val, date_str, start_dt, end_dt
        )
        if bars_df.empty and db_bars:
            # Fall back to whatever we have in DB if live fetch failed
            bars_df = pd.DataFrame(db_bars).set_index("time")
            records_to_insert = []
    else:
        if db_bars:
            bars_df = pd.DataFrame(db_bars).set_index("time")
            records_to_insert = []
        else:
            bars_df, records_to_insert = await asyncio.to_thread(
                _fetch_with_fallback, ticker_val, date_str, start_dt, end_dt
            )

    if bars_df.empty:
        raise ChartDataNotFoundError(ticker_val, date_str)

    result, _ = await asyncio.to_thread(_compute_indicators, bars_df, mini)

    if records_to_insert:
        try:
            from fastapi_app.db.ohlcv import insert_bars_1min
            async with db.transaction():
                await insert_bars_1min(db, records_to_insert)
        except Exception as exc:
            log.error("Failed to cache fetched chart data in DB: %s", exc)

    return result


# ---------------------------------------------------------------------------
# DB read
# ---------------------------------------------------------------------------

async def _read_db_bars(
    db: asyncpg.Connection, ticker: str, start_dt: datetime, end_dt: datetime
) -> list[dict]:
    """Read 1-minute bars from TimescaleDB. Returns [] on any error."""
    try:
        rows = await db.fetch(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM price_history_1min
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp <= $3
            ORDER BY timestamp ASC
            """,
            ticker,
            start_dt,
            end_dt,
        )
    except Exception as exc:
        log.error("Failed to query price_history_1min for chart-data: %s", exc)
        return []
    return [
        {
            "time": r["timestamp"],
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": r["volume"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# External fetch fallback chain (sync; called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _fetch_with_fallback(
    ticker: str, date_str: str, start_dt: datetime, end_dt: datetime
) -> tuple[pd.DataFrame, list[tuple]]:
    """
    Run the full fallback chain: Schwab → Polygon → yfinance → prev-day Polygon
    → prev-day yfinance. Returns (bars_df, records_to_insert). The records list
    is non-empty only when bars came from an external source (so the caller
    can cache them in DB).
    """
    # 1. Schwab
    bars_df = _try_schwab(ticker, start_dt, end_dt)
    # 2. Polygon
    if bars_df.empty:
        bars_df = _fetch_intraday_polygon(ticker, date_str)
    # 3. yfinance
    if bars_df.empty:
        bars_df = _try_yfinance(ticker, date_str)
    # 4. Previous day fallback
    if bars_df.empty:
        try:
            prev_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            prev_date = None
        if prev_date:
            bars_df = _fetch_intraday_polygon(ticker, prev_date)
            if bars_df.empty:
                bars_df = _try_yfinance(ticker, prev_date)

    if bars_df.empty:
        return bars_df, []

    records_to_insert = _bars_to_insert_records(bars_df, ticker)
    return bars_df, records_to_insert


def _try_schwab(ticker: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    try:
        from services.schwab_client import get_price_history_every_minute
        candles = get_price_history_every_minute(ticker, start_datetime=start_dt, end_datetime=end_dt)
    except Exception as exc:
        log.error("Failed to fetch from Schwab in chart-data fallback: %s", exc)
        return pd.DataFrame()
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles).rename(columns={"datetime": "t"})
    df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    return df.set_index("timestamp")


def _try_yfinance(ticker: str, date_str: str) -> pd.DataFrame:
    try:
        start = datetime.strptime(date_str, "%Y-%m-%d")
        end = start + timedelta(days=1)
        df = yf_download_safe(ticker, start, end)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    return df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})


def yf_download_safe(ticker: str, start: datetime, end: datetime):
    """Isolated to allow tests to monkeypatch yfinance.download."""
    import yfinance as yf
    return yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1m",
        prepost=True,
        progress=False,
    )


def _fetch_intraday_polygon(ticker: str, date: str) -> pd.DataFrame:
    """
    Moved verbatim from tasks/llm_tasks.py:_fetch_intraday_polygon so the
    indicator pipeline no longer reaches into a Celery task module.
    """
    from services.schwab_client import get_minute_bars
    try:
        bars = get_minute_bars(ticker, date, date, limit=50_000)
        if not bars:
            return pd.DataFrame()
        df = pd.DataFrame(bars)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                                "c": "close", "v": "volume", "vw": "vwap"})
        df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")
        return df.set_index("timestamp")
    except Exception as exc:
        print(f"[chart_data_service] Massive/Polygon intraday fetch failed for {ticker} {date}: {exc}")
        return pd.DataFrame()


def _bars_to_insert_records(bars_df: pd.DataFrame, ticker: str) -> list[tuple]:
    """Convert a bars DataFrame into (symbol, ts, o, h, l, c, v) tuples for DB insert."""
    records: list[tuple] = []
    for idx, row in bars_df.iterrows():
        ts = idx.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        else:
            ts = ts.astimezone(UTC)
        records.append((
            ticker,
            ts,
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            int(row["volume"]) if pd.notna(row["volume"]) else 0,
        ))
    return records


# ---------------------------------------------------------------------------
# Indicator computation (pure; sync)
# ---------------------------------------------------------------------------

def _compute_indicators(bars_df: pd.DataFrame, mini_mode: bool) -> tuple[dict, list]:
    """
    Compute the indicator series + the Lightweight-Charts payload shape.
    Returns (payload, records_to_insert). records_to_insert is always []
    for this code path; the caller already built the insert list before
    calling us.
    """
    df = bars_df[["open", "high", "low", "close", "volume"]].copy()

    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert("UTC")
    else:
        df.index = df.index.tz_localize("UTC", ambiguous="infer", nonexistent="shift_forward")
    df["time"] = ((df.index - EPOCH).total_seconds()).astype(int)

    if mini_mode:
        df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_100"] = df["close"].ewm(span=100, adjust=False).mean()
        df = df.dropna(subset=["ema_21"])
    else:
        for span in (8, 13, 21, 34, 55):
            df[f"ema_{span}"] = df["close"].ewm(span=span, adjust=False).mean()

        vol_avg = df["volume"].rolling(20).mean()
        df["rvol"] = (df["volume"] / vol_avg).fillna(1.0)

        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

        up_move = df["high"] - df["high"].shift(1)
        down_move = df["low"].shift(1) - df["low"]
        pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        pos_dm_s = pd.Series(pos_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean()
        neg_dm_s = pd.Series(neg_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean()
        tr_s = tr.ewm(alpha=1 / 14, adjust=False).mean()
        df["plus_di"] = 100 * (pos_dm_s / tr_s)
        df["minus_di"] = 100 * (neg_dm_s / tr_s)
        dx = 100 * (df["plus_di"] - df["minus_di"]).abs() / (df["plus_di"] + df["minus_di"]).abs()
        df["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
        df = df.dropna(subset=["ema_55", "adx"])

    t = df["time"].tolist()

    def line_series(col: str) -> list[dict]:
        return [
            {"time": int(ti), "value": round(float(v), 4)}
            for ti, v in zip(t, df[col])
            if not (isinstance(v, float) and v != v)
        ]

    ohlcv_records = [
        {
            "time": int(ti),
            "open": round(float(o), 4),
            "high": round(float(h), 4),
            "low": round(float(l), 4),
            "close": round(float(c), 4),
        }
        for ti, o, h, l, c in zip(t, df["open"], df["high"], df["low"], df["close"])
    ]
    vol_colors = [
        "rgba(34,211,167,0.5)" if c >= o else "rgba(240,77,90,0.5)"
        for c, o in zip(df["close"], df["open"])
    ]
    vol_records = [
        {"time": int(ti), "value": int(v), "color": col}
        for ti, v, col in zip(t, df["volume"], vol_colors)
    ]

    if mini_mode:
        return {
            "ohlcv": ohlcv_records,
            "volume": vol_records,
            "ema_21": line_series("ema_21"),
            "ema_50": line_series("ema_50"),
            "ema_100": line_series("ema_100"),
        }, []

    return {
        "ohlcv": ohlcv_records,
        "volume": vol_records,
        "rvol": line_series("rvol"),
        "ema_8": line_series("ema_8"),
        "ema_13": line_series("ema_13"),
        "ema_21": line_series("ema_21"),
        "ema_34": line_series("ema_34"),
        "ema_55": line_series("ema_55"),
        "adx": line_series("adx"),
        "plus_di": line_series("plus_di"),
        "minus_di": line_series("minus_di"),
        "atr": line_series("atr"),
    }, []
