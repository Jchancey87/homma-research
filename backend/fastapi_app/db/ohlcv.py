"""
fastapi_app/db/ohlcv.py
Read/write helpers for price history tables (TimescaleDB hypertables).

Tables:
  - price_history_1min  — intraday 1-minute bars  (symbol, timestamp, OHLCV)
  - price_history_daily — end-of-day bars          (symbol, date, OHLCV)

Uses the raw asyncpg pool from db.core.  All functions accept an asyncpg
Connection as their first argument (from Depends(get_db)).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def insert_bars_1min(
    conn: asyncpg.Connection,
    records: list[tuple],
) -> int:
    """
    Bulk-insert 1-minute OHLCV bars via asyncpg COPY (fastest method).

    Each record is a tuple: (symbol, timestamp, open, high, low, close, volume)
    where timestamp is a timezone-aware datetime.

    Returns the number of rows inserted.  Duplicates on (symbol, timestamp)
    are silently skipped via ON CONFLICT.
    """
    if not records:
        return 0

    # COPY is fastest but doesn't support ON CONFLICT, so we use a temp table
    # to stage data, then merge into the real table.
    await conn.execute("""
        CREATE TEMP TABLE _tmp_bars_1min (
            symbol    VARCHAR(10),
            timestamp TIMESTAMPTZ,
            open      DOUBLE PRECISION,
            high      DOUBLE PRECISION,
            low       DOUBLE PRECISION,
            close     DOUBLE PRECISION,
            volume    BIGINT
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table(
        "_tmp_bars_1min",
        records=records,
        columns=["symbol", "timestamp", "open", "high", "low", "close", "volume"],
    )

    result = await conn.execute("""
        INSERT INTO price_history_1min (symbol, timestamp, open, high, low, close, volume)
        SELECT symbol, timestamp, open, high, low, close, volume
        FROM _tmp_bars_1min
        ON CONFLICT (symbol, timestamp) DO NOTHING
    """)

    count = int(result.split()[-1])
    log.info("[ohlcv] Inserted %d 1-min bars", count)
    return count


async def insert_bars_daily(
    conn: asyncpg.Connection,
    records: list[tuple],
) -> int:
    """
    Bulk-insert daily OHLCV bars.

    Each record is a tuple: (symbol, date, open, high, low, close, volume)
    where date is a datetime.date.

    Returns the number of rows inserted.  Duplicates silently skipped.
    """
    if not records:
        return 0

    await conn.execute("""
        CREATE TEMP TABLE _tmp_bars_daily (
            symbol VARCHAR(10),
            date   DATE,
            open   DOUBLE PRECISION,
            high   DOUBLE PRECISION,
            low    DOUBLE PRECISION,
            close  DOUBLE PRECISION,
            volume BIGINT
        ) ON COMMIT DROP
    """)

    await conn.copy_records_to_table(
        "_tmp_bars_daily",
        records=records,
        columns=["symbol", "date", "open", "high", "low", "close", "volume"],
    )

    result = await conn.execute("""
        INSERT INTO price_history_daily (symbol, date, open, high, low, close, volume)
        SELECT symbol, date, open, high, low, close, volume
        FROM _tmp_bars_daily
        ON CONFLICT (symbol, date) DO NOTHING
    """)

    count = int(result.split()[-1])
    log.info("[ohlcv] Inserted %d daily bars", count)
    return count


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def get_bars_1min(
    conn: asyncpg.Connection,
    symbol: str,
    start: datetime,
    end: datetime,
    limit: int = 50_000,
) -> list[dict]:
    """
    Fetch 1-minute bars for a symbol within a time range.

    Uses TimescaleDB's chunk-pruning on the designated timestamp column
    for fast range scans.
    """
    rows = await conn.fetch(
        """
        SELECT symbol, timestamp, open, high, low, close, volume
        FROM price_history_1min
        WHERE symbol = $1
          AND timestamp >= $2
          AND timestamp <= $3
        ORDER BY timestamp ASC
        LIMIT $4
        """,
        symbol, start, end, limit,
    )
    return [dict(r) for r in rows]


async def get_bars_daily(
    conn: asyncpg.Connection,
    symbol: str,
    start: date,
    end: date,
    limit: int = 10_000,
) -> list[dict]:
    """Fetch daily bars for a symbol within a date range."""
    rows = await conn.fetch(
        """
        SELECT symbol, date, open, high, low, close, volume
        FROM price_history_daily
        WHERE symbol = $1
          AND date >= $2
          AND date <= $3
        ORDER BY date ASC
        LIMIT $4
        """,
        symbol, start, end, limit,
    )
    return [dict(r) for r in rows]


async def get_latest_bar_daily(
    conn: asyncpg.Connection,
    symbol: str,
) -> dict | None:
    """Fetch the most recent daily bar for a symbol."""
    row = await conn.fetchrow(
        """
        SELECT symbol, date, open, high, low, close, volume
        FROM price_history_daily
        WHERE symbol = $1
        ORDER BY date DESC
        LIMIT 1
        """,
        symbol,
    )
    return dict(row) if row else None


async def resample_1min(
    conn: asyncpg.Connection,
    symbol: str,
    bucket: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """
    Resample 1-minute bars into a higher timeframe using time_bucket().

    Args:
        bucket: PostgreSQL interval string, e.g. '5 minutes', '1 hour', '1 day'
    """
    # Validate bucket to prevent SQL injection — must be a valid interval format
    _allowed_chars = set("0123456789 minuteshourdaywek")
    if not all(c in _allowed_chars for c in bucket.lower()):
        raise ValueError(f"Invalid bucket interval: {bucket!r}")

    rows = await conn.fetch(
        f"""
        SELECT
            time_bucket('{bucket}'::INTERVAL, timestamp) AS ts,
            first(open, timestamp)  AS open,
            max(high)               AS high,
            min(low)                AS low,
            last(close, timestamp)  AS close,
            sum(volume)             AS volume
        FROM price_history_1min
        WHERE symbol = $1
          AND timestamp >= $2
          AND timestamp <= $3
        GROUP BY ts
        ORDER BY ts ASC
        """,
        symbol, start, end,
    )
    return [dict(r) for r in rows]


async def get_bar_counts(conn: asyncpg.Connection) -> list[dict]:
    """Summary of bar counts per symbol (useful for monitoring backfill status)."""
    rows = await conn.fetch("""
        SELECT 'daily' AS timeframe, symbol, count(*) AS bar_count,
               min(date)::text AS first_date, max(date)::text AS last_date
        FROM price_history_daily
        GROUP BY symbol
        UNION ALL
        SELECT '1min' AS timeframe, symbol, count(*) AS bar_count,
               min(timestamp)::text AS first_date, max(timestamp)::text AS last_date
        FROM price_history_1min
        GROUP BY symbol
        ORDER BY timeframe, symbol
    """)
    return [dict(r) for r in rows]
