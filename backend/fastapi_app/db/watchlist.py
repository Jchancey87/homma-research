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
from datetime import datetime, timezone, date
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def list_watchlist(conn: asyncpg.Connection, group_id: Optional[int] = None) -> list[dict]:
    """All watchlist tickers, optionally filtered by group_id."""
    if group_id is not None:
        if group_id == 0:
            rows = await conn.fetch(
                "SELECT * FROM watchlist WHERE group_id IS NULL "
                "ORDER BY last_viewed_at DESC NULLS LAST, added_at DESC"
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM watchlist WHERE group_id = $1 "
                "ORDER BY last_viewed_at DESC NULLS LAST, added_at DESC",
                group_id
            )
    else:
        rows = await conn.fetch(
            "SELECT * FROM watchlist "
            "ORDER BY last_viewed_at DESC NULLS LAST, added_at DESC"
        )
    return [dict(r) for r in rows]


async def list_watchlist_tickers(conn: asyncpg.Connection, group_id: Optional[int] = None) -> list[str]:
    """Just the ticker symbols, optionally filtered by group_id."""
    if group_id is not None:
        if group_id == 0:
            rows = await conn.fetch(
                "SELECT ticker FROM watchlist WHERE group_id IS NULL ORDER BY added_at DESC"
            )
        else:
            rows = await conn.fetch(
                "SELECT ticker FROM watchlist WHERE group_id = $1 ORDER BY added_at DESC",
                group_id
            )
    else:
        rows = await conn.fetch("SELECT ticker FROM watchlist ORDER BY added_at DESC")
    return [r["ticker"] for r in rows]


async def watchlist_ticker_exists(
    conn: asyncpg.Connection,
    ticker: str,
    group_id: Optional[int] = None,
) -> bool:
    if group_id is None:
        row = await conn.fetchrow(
            "SELECT 1 FROM watchlist WHERE ticker = $1 AND group_id IS NULL",
            ticker
        )
    else:
        row = await conn.fetchrow(
            "SELECT 1 FROM watchlist WHERE ticker = $1 AND group_id = $2",
            ticker, group_id
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
    group_id: Optional[int] = None,
    runway_months: Optional[float] = None,
    dilution_risk: Optional[str] = None,
    upcoming_catalyst: Optional[str] = None,
    catalyst_date: Optional[date] = None,
) -> None:
    """
    Insert a new watchlist row. Raises ``asyncpg.UniqueViolationError``
    if the ticker is already on the watchlist in this group.
    """
    await conn.execute(
        "INSERT INTO watchlist (ticker, sector, notes, tags, group_id, added_at, runway_months, dilution_risk, upcoming_catalyst, catalyst_date) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
        ticker, sector, notes, tags_json, group_id, datetime.now(timezone.utc), runway_months, dilution_risk, upcoming_catalyst, catalyst_date
    )


async def upsert_watchlist(
    conn: asyncpg.Connection,
    *,
    ticker: str,
    sector: Optional[str],
    notes: Optional[str],
    tags_json: str,
    group_id: Optional[int] = None,
    runway_months: Optional[float] = None,
    dilution_risk: Optional[str] = None,
    upcoming_catalyst: Optional[str] = None,
    catalyst_date: Optional[date] = None,
) -> None:
    """
    Insert a watchlist row, or update notes/sector/tags if it already exists in the group.
    """
    if group_id is None:
        row = await conn.fetchrow(
            "SELECT 1 FROM watchlist WHERE ticker = $1 AND group_id IS NULL",
            ticker
        )
    else:
        row = await conn.fetchrow(
            "SELECT 1 FROM watchlist WHERE ticker = $1 AND group_id = $2",
            ticker, group_id
        )

    if row:
        if group_id is None:
            await conn.execute(
                "UPDATE watchlist SET "
                "sector = COALESCE($1, sector), "
                "notes = COALESCE($2, notes), "
                "tags = $3, "
                "runway_months = COALESCE($4, runway_months), "
                "dilution_risk = COALESCE($5, dilution_risk), "
                "upcoming_catalyst = COALESCE($6, upcoming_catalyst), "
                "catalyst_date = COALESCE($7, catalyst_date) "
                "WHERE ticker = $8 AND group_id IS NULL",
                sector, notes, tags_json, runway_months, dilution_risk, upcoming_catalyst, catalyst_date, ticker
            )
        else:
            await conn.execute(
                "UPDATE watchlist SET "
                "sector = COALESCE($1, sector), "
                "notes = COALESCE($2, notes), "
                "tags = $3, "
                "runway_months = COALESCE($4, runway_months), "
                "dilution_risk = COALESCE($5, dilution_risk), "
                "upcoming_catalyst = COALESCE($6, upcoming_catalyst), "
                "catalyst_date = COALESCE($7, catalyst_date) "
                "WHERE ticker = $8 AND group_id = $9",
                sector, notes, tags_json, runway_months, dilution_risk, upcoming_catalyst, catalyst_date, ticker, group_id
            )
    else:
        await conn.execute(
            "INSERT INTO watchlist (ticker, sector, notes, tags, group_id, added_at, runway_months, dilution_risk, upcoming_catalyst, catalyst_date) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
            ticker, sector, notes, tags_json, group_id, datetime.now(timezone.utc), runway_months, dilution_risk, upcoming_catalyst, catalyst_date
        )


async def update_watchlist(
    conn: asyncpg.Connection,
    ticker: str,
    updates: dict,
    group_id: Optional[int] = None,
) -> bool:
    """
    Patch a watchlist row. ``updates`` is a dict of {column: value}
    pairs. Returns True if a row was updated, False otherwise.
    """
    if not updates:
        return await watchlist_ticker_exists(conn, ticker, group_id)

    set_parts = [f"{k} = ${i + 1}" for i, k in enumerate(updates)]
    values = list(updates.values())
    
    if group_id is None:
        query = (
            f"UPDATE watchlist SET {', '.join(set_parts)} "
            f"WHERE ticker = ${len(values) + 1} AND group_id IS NULL"
        )
        result = await conn.execute(query, *values, ticker)
    else:
        query = (
            f"UPDATE watchlist SET {', '.join(set_parts)} "
            f"WHERE ticker = ${len(values) + 1} AND group_id = ${len(values) + 2}"
        )
        result = await conn.execute(query, *values, ticker, group_id)
        
    return not result.endswith(" 0")


async def mark_watchlist_viewed(
    conn: asyncpg.Connection,
    ticker: str,
    viewed_at: Optional[datetime] = None,
    group_id: Optional[int] = None,
) -> bool:
    """Stamp ``last_viewed_at`` for the given ticker in the group. Returns True if updated."""
    when = viewed_at or datetime.now(timezone.utc)
    if group_id is None:
        result = await conn.execute(
            "UPDATE watchlist SET last_viewed_at = $1 WHERE ticker = $2 AND group_id IS NULL",
            when, ticker,
        )
    else:
        result = await conn.execute(
            "UPDATE watchlist SET last_viewed_at = $1 WHERE ticker = $2 AND group_id = $3",
            when, ticker, group_id,
        )
    return not result.endswith(" 0")


async def delete_watchlist(
    conn: asyncpg.Connection,
    ticker: str,
    group_id: Optional[int] = None,
) -> bool:
    """Delete the watchlist row in the group. Returns True if a row was deleted."""
    if group_id is None:
        result = await conn.execute("DELETE FROM watchlist WHERE ticker = $1 AND group_id IS NULL", ticker)
    else:
        result = await conn.execute("DELETE FROM watchlist WHERE ticker = $1 AND group_id = $2", ticker, group_id)
    return not result.endswith(" 0")


async def update_watchlist_metrics(
    conn: asyncpg.Connection,
    ticker: str,
    *,
    runway_months: Optional[float],
    dilution_risk: Optional[str],
    upcoming_catalyst: Optional[str],
    catalyst_date: Optional[date],
    group_id: Optional[int] = None,
) -> bool:
    """Update biotech enrichment metrics for a watchlist ticker."""
    if group_id is not None:
        if group_id == 0:
            result = await conn.execute(
                "UPDATE watchlist SET runway_months = $1, dilution_risk = $2, "
                "upcoming_catalyst = $3, catalyst_date = $4 "
                "WHERE ticker = $5 AND group_id IS NULL",
                runway_months, dilution_risk, upcoming_catalyst, catalyst_date, ticker
            )
        else:
            result = await conn.execute(
                "UPDATE watchlist SET runway_months = $1, dilution_risk = $2, "
                "upcoming_catalyst = $3, catalyst_date = $4 "
                "WHERE ticker = $5 AND group_id = $6",
                runway_months, dilution_risk, upcoming_catalyst, catalyst_date, ticker, group_id
            )
    else:
        result = await conn.execute(
            "UPDATE watchlist SET runway_months = $1, dilution_risk = $2, "
            "upcoming_catalyst = $3, catalyst_date = $4 "
            "WHERE ticker = $5",
            runway_months, dilution_risk, upcoming_catalyst, catalyst_date, ticker
        )
    return not result.endswith(" 0")


# ---------------------------------------------------------------------------
# Watchlist Groups
# ---------------------------------------------------------------------------

async def list_watchlist_groups(conn: asyncpg.Connection) -> list[dict]:
    """All watchlist groups, ordered alphabetically."""
    rows = await conn.fetch("SELECT * FROM watchlist_groups ORDER BY name ASC")
    return [dict(r) for r in rows]


async def watchlist_group_exists_by_name(conn: asyncpg.Connection, name: str) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM watchlist_groups WHERE name = $1", name)
    return row is not None


async def insert_watchlist_group(conn: asyncpg.Connection, name: str) -> dict:
    row = await conn.fetchrow(
        "INSERT INTO watchlist_groups (name) VALUES ($1) RETURNING *",
        name
    )
    return dict(row)


async def delete_watchlist_group(conn: asyncpg.Connection, group_id: int) -> bool:
    result = await conn.execute("DELETE FROM watchlist_groups WHERE id = $1", group_id)
    return not result.endswith(" 0")


async def init_reflections_table(conn: asyncpg.Connection) -> None:
    """Create the continuation_reflections table if it does not already exist."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS continuation_reflections (
            id SERIAL PRIMARY KEY,
            date DATE UNIQUE NOT NULL,
            reflection_text TEXT NOT NULL,
            lessons_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

