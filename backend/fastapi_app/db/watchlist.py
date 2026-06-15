"""
fastapi_app/db/watchlist.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read/write helpers for the ``watchlist`` table.

Table: watchlist
Columns: id, ticker (UNIQUE), sector, notes, tags (JSON array string),
         alert_threshold, added_at, last_viewed_at

Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain
dicts/lists/booleans so routers stay Router-Layer-Rules compliant.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def list_watchlist(conn: asyncpg.Connection) -> list[dict]:
    """All watchlist tickers, ordered by last viewed (newest first) then added."""
    rows = await conn.fetch(
        "SELECT * FROM watchlist "
        "ORDER BY last_viewed_at DESC NULLS LAST, added_at DESC"
    )
    return [dict(r) for r in rows]


async def list_watchlist_tickers(conn: asyncpg.Connection) -> list[str]:
    """Just the ticker symbols, ordered by added_at DESC.  Used by the
    batch-price endpoint to avoid fetching the full row payload."""
    rows = await conn.fetch("SELECT ticker FROM watchlist ORDER BY added_at DESC")
    return [r["ticker"] for r in rows]


async def watchlist_ticker_exists(conn: asyncpg.Connection, ticker: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM watchlist WHERE ticker = $1", ticker
    )
    return row is not None


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def insert_watchlist(
    conn: asyncpg.Connection,
    *,
    ticker: str,
    sector: Optional[str],
    notes: Optional[str],
    tags_json: str,
) -> None:
    """
    Insert a new watchlist row.  Raises ``asyncpg.UniqueViolationError``
    if the ticker is already on the watchlist; callers translate that
    to an HTTP 409.
    """
    await conn.execute(
        "INSERT INTO watchlist (ticker, sector, notes, tags, added_at) "
        "VALUES ($1, $2, $3, $4, $5)",
        ticker, sector, notes, tags_json, datetime.now(timezone.utc),
    )


async def update_watchlist(
    conn: asyncpg.Connection,
    ticker: str,
    updates: dict,
) -> bool:
    """
    Patch a watchlist row.  ``updates`` is a dict of {column: value}
    pairs containing only fields the caller wants to change.  Returns
    True if a row was updated, False otherwise.
    """
    if not updates:
        return await watchlist_ticker_exists(conn, ticker)

    set_parts = [f"{k} = ${i + 1}" for i, k in enumerate(updates)]
    values = list(updates.values()) + [ticker]
    result = await conn.execute(
        f"UPDATE watchlist SET {', '.join(set_parts)} "
        f"WHERE ticker = ${len(values)}",
        *values,
    )
    return not result.endswith(" 0")


async def mark_watchlist_viewed(
    conn: asyncpg.Connection,
    ticker: str,
    viewed_at: Optional[datetime] = None,
) -> bool:
    """Stamp ``last_viewed_at`` for the given ticker.  Returns True if updated."""
    when = viewed_at or datetime.now(timezone.utc)
    result = await conn.execute(
        "UPDATE watchlist SET last_viewed_at = $1 WHERE ticker = $2",
        when, ticker,
    )
    return not result.endswith(" 0")


async def delete_watchlist(conn: asyncpg.Connection, ticker: str) -> bool:
    """Delete the watchlist row.  Returns True if a row was deleted."""
    result = await conn.execute("DELETE FROM watchlist WHERE ticker = $1", ticker)
    return not result.endswith(" 0")
