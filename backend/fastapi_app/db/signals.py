"""
fastapi_app/db/signals.py
Read/write helpers for the signals table.

Table: signals (regular table with FK to strategies)
Columns: id, ts, symbol, strategy_id, signal_type, timeframe,
         price, stop_loss, take_profit, confidence, metadata
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)


def _parse_signal_row(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    if "metadata" in d and isinstance(d["metadata"], str):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (ValueError, TypeError):
            pass
    return d



# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def insert_signal(
    conn: asyncpg.Connection,
    symbol: str,
    signal_type: str,
    price: float,
    strategy_id: Optional[int] = None,
    timeframe: Optional[str] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    confidence: Optional[float] = None,
    metadata: Optional[dict] = None,
    ts: Optional[datetime] = None,
) -> int:
    """
    Insert a single trade signal and return its ID.

    signal_type should be one of: 'ENTRY_LONG', 'ENTRY_SHORT', 'EXIT', 'ALERT'
    """
    if ts is None:
        ts = datetime.now(tz=timezone.utc)
    meta_json = json.dumps(metadata) if metadata else "{}"

    row = await conn.fetchrow(
        """
        INSERT INTO signals
            (ts, symbol, strategy_id, signal_type, timeframe,
             price, stop_loss, take_profit, confidence, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
        RETURNING id
        """,
        ts, symbol, strategy_id, signal_type, timeframe,
        price, stop_loss, take_profit, confidence, meta_json,
    )
    signal_id = row["id"]
    log.info("[signals] Created signal %d: %s %s @ %.2f", signal_id, signal_type, symbol, price)
    return signal_id


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def get_signals(
    conn: asyncpg.Connection,
    symbol: Optional[str] = None,
    limit: int = 50,
    signal_type: Optional[str] = None,
    strategy_id: Optional[int] = None,
) -> list[dict]:
    """
    Fetch recent signals, optionally filtered by symbol, type, or strategy.
    Includes strategy name via JOIN.
    """
    conditions = []
    params: list = []

    if symbol:
        conditions.append(f"s.symbol = ${len(params)+1}")
        params.append(symbol.upper().strip())
    if signal_type:
        conditions.append(f"s.signal_type = ${len(params)+1}")
        params.append(signal_type)
    if strategy_id is not None:
        conditions.append(f"s.strategy_id = ${len(params)+1}")
        params.append(strategy_id)

    limit_param_idx = len(params) + 1
    params.append(limit)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    rows = await conn.fetch(
        f"""
        SELECT s.id, s.ts, s.symbol, s.signal_type, s.timeframe,
               s.price, s.stop_loss, s.take_profit, s.confidence,
               s.metadata, s.strategy_id,
               st.name AS strategy_name
        FROM signals s
        LEFT JOIN strategies st ON s.strategy_id = st.id
        {where}
        ORDER BY s.ts DESC
        LIMIT ${limit_param_idx}
        """,
        *params,
    )
    return [_parse_signal_row(r) for r in rows if r is not None]


async def get_signal_by_id(
    conn: asyncpg.Connection,
    signal_id: int,
) -> dict | None:
    """Fetch a single signal by ID with strategy name."""
    row = await conn.fetchrow(
        """
        SELECT s.*, st.name AS strategy_name
        FROM signals s
        LEFT JOIN strategies st ON s.strategy_id = st.id
        WHERE s.id = $1
        """,
        signal_id,
    )
    return _parse_signal_row(row)
