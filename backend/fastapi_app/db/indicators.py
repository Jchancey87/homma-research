"""
fastapi_app/db/indicators.py
Read/write helpers for the indicators hypertable.

Table: indicators (TimescaleDB hypertable, compressed after 14 days)
Columns: ts, symbol, timeframe, indicator_name, value, value2, value3
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def insert_indicators(
    conn: asyncpg.Connection,
    records: list[tuple],
) -> int:
    """
    Bulk-insert indicator values.

    Each record is a tuple:
        (ts, symbol, timeframe, indicator_name, value, value2, value3)

    value2/value3 can be None for single-output indicators.
    No uniqueness constraint — callers should avoid inserting duplicates.
    """
    if not records:
        return 0

    await conn.copy_records_to_table(
        "indicators",
        records=records,
        columns=["ts", "symbol", "timeframe", "indicator_name",
                 "value", "value2", "value3"],
    )
    log.info("[indicators] Inserted %d rows", len(records))
    return len(records)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def get_indicator(
    conn: asyncpg.Connection,
    symbol: str,
    indicator_name: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    limit: int = 50_000,
) -> list[dict]:
    """Fetch values for a specific indicator on a symbol within a time range."""
    rows = await conn.fetch(
        """
        SELECT ts, value, value2, value3
        FROM indicators
        WHERE symbol = $1
          AND indicator_name = $2
          AND timeframe = $3
          AND ts >= $4
          AND ts <= $5
        ORDER BY ts ASC
        LIMIT $6
        """,
        symbol, indicator_name, timeframe, start, end, limit,
    )
    return [dict(r) for r in rows]


async def get_indicators_multi(
    conn: asyncpg.Connection,
    symbol: str,
    indicator_names: list[str],
    timeframe: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """
    Fetch multiple indicators at once for overlaying on a chart.
    Returns rows with indicator_name column to differentiate.
    """
    rows = await conn.fetch(
        """
        SELECT ts, indicator_name, value, value2, value3
        FROM indicators
        WHERE symbol = $1
          AND indicator_name = ANY($2)
          AND timeframe = $3
          AND ts >= $4
          AND ts <= $5
        ORDER BY ts ASC, indicator_name
        """,
        symbol, indicator_names, timeframe, start, end,
    )
    return [dict(r) for r in rows]


async def get_latest_indicator(
    conn: asyncpg.Connection,
    symbol: str,
    indicator_name: str,
    timeframe: str,
) -> dict | None:
    """Fetch the most recent value for a specific indicator."""
    row = await conn.fetchrow(
        """
        SELECT ts, value, value2, value3
        FROM indicators
        WHERE symbol = $1
          AND indicator_name = $2
          AND timeframe = $3
        ORDER BY ts DESC
        LIMIT 1
        """,
        symbol, indicator_name, timeframe,
    )
    return dict(row) if row else None
