"""
fastapi_app/db/continuation_picks.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read/write helpers for the ``continuation_picks`` table.

Table: continuation_picks
Columns: id, ticker, date, reason, gap_pct, float_shares, rvol_15m,
         sector, rank, is_active, deactivated_at, deactivated_reason,
         created_at, plus D0/D1/D2/D3 OHLCV + fundamental enrichment
         columns populated by services.continuation_performance_service.

The performance analytics (forward returns, win-rate breakdown) live
in ``services.continuation_analytics``; this module only owns the
plain CRUD the router needs.

Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain
dicts/lists/booleans so routers stay Router-Layer-Rules compliant.
"""
from __future__ import annotations

import datetime
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def list_picks(
    conn: asyncpg.Connection,
    *,
    include_inactive: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Latest continuation picks, optionally including deactivated ones."""
    if include_inactive:
        rows = await conn.fetch(
            """SELECT * FROM continuation_picks
               ORDER BY is_active DESC, date DESC, rank ASC
               LIMIT $1""",
            limit,
        )
    else:
        rows = await conn.fetch(
            """SELECT * FROM continuation_picks
               WHERE is_active = TRUE
               ORDER BY date DESC, rank ASC
               LIMIT $1""",
            limit,
        )
    return [dict(r) for r in rows]


async def picks_stats_last_14_days(conn: asyncpg.Connection) -> list[dict]:
    """Per-day active pick counts for the last 14 days, newest first."""
    rows = await conn.fetch(
        """SELECT date, COUNT(*) AS count
           FROM continuation_picks
           WHERE is_active = TRUE
           GROUP BY date
           ORDER BY date DESC
           LIMIT 14"""
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def insert_pick(
    conn: asyncpg.Connection,
    *,
    ticker: str,
    date: str,                       # YYYY-MM-DD
    reason: Optional[str],
    gap_pct: Optional[float],
    float_shares: Optional[float],
    rvol_15m: Optional[float],
    sector: Optional[str],
    rank: int,
    created_at: datetime.datetime,
) -> bool:
    """
    Insert one continuation pick.  Idempotent via
    ``ON CONFLICT (ticker, date) DO NOTHING`` — returns True if a new
    row was inserted, False if it was a duplicate.
    """
    result = await conn.execute(
        """INSERT INTO continuation_picks
           (ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank, created_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           ON CONFLICT (ticker, date) DO NOTHING""",
        ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank, created_at,
    )
    # asyncpg returns "INSERT 0 <n>"; a duplicate returns "INSERT 0 0".
    parts = result.split()
    return len(parts) >= 3 and parts[2] != "0"


async def deactivate_pick(
    conn: asyncpg.Connection,
    pick_id: int,
    reason: str,
    deactivated_at: datetime.datetime,
) -> bool:
    """Mark a pick inactive with a reason.  Returns True if a row was updated."""
    result = await conn.execute(
        """UPDATE continuation_picks
           SET is_active = FALSE, deactivated_at = $1, deactivated_reason = $2
           WHERE id = $3""",
        deactivated_at, reason, pick_id,
    )
    return not result.endswith(" 0")


async def delete_pick(conn: asyncpg.Connection, pick_id: int) -> bool:
    """Hard-delete a pick by id.  Returns True if a row was deleted."""
    result = await conn.execute("DELETE FROM continuation_picks WHERE id = $1", pick_id)
    return not result.endswith(" 0")


async def pick_exists(conn: asyncpg.Connection, pick_id: int) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM continuation_picks WHERE id = $1", pick_id)
    return row is not None
