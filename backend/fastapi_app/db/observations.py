"""
fastapi_app/db/observations.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read/write helpers for the ``observations`` table.

Table: observations
Columns: id, ticker, date, title, body, sentiment, tags (JSON string),
         linked_chart_id, created_at, updated_at

Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain
dicts/ints/booleans so routers stay Router-Layer-Rules compliant.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def list_observations(
    conn: asyncpg.Connection,
    *,
    ticker: Optional[str] = None,
    sentiment: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """
    List observations matching the optional filters, newest first.
    ``tag`` is a case-insensitive substring match against the JSON array.
    """
    conditions: list[str] = []
    params: list = []

    if ticker:
        conditions.append(f"ticker = ${len(params) + 1}")
        params.append(ticker)
    if sentiment:
        conditions.append(f"sentiment = ${len(params) + 1}")
        params.append(sentiment)
    if tag:
        conditions.append(f"tags ILIKE ${len(params) + 1}")
        params.append(f"%{tag}%")
    if date_from:
        conditions.append(f"date >= ${len(params) + 1}")
        params.append(date_from)
    if date_to:
        conditions.append(f"date <= ${len(params) + 1}")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)
    rows = await conn.fetch(
        f"SELECT * FROM observations {where} "
        f"ORDER BY date DESC, created_at DESC LIMIT ${len(params)}",
        *params,
    )
    return [dict(r) for r in rows]


async def list_observations_for_ticker(
    conn: asyncpg.Connection,
    ticker: str,
) -> list[dict]:
    """All observations for a single ticker, newest first."""
    rows = await conn.fetch(
        "SELECT * FROM observations WHERE ticker = $1 "
        "ORDER BY date DESC, created_at DESC",
        ticker,
    )
    return [dict(r) for r in rows]


async def get_observation_by_id(
    conn: asyncpg.Connection,
    obs_id: int,
) -> dict | None:
    """Fetch a single observation by id, or None if not found."""
    row = await conn.fetchrow(
        "SELECT * FROM observations WHERE id = $1", obs_id
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def create_observation(
    conn: asyncpg.Connection,
    *,
    ticker: str,
    date: str,                # YYYY-MM-DD
    title: Optional[str],
    body: str,
    sentiment: str,
    tags: list[str],
    linked_chart_id: Optional[int],
) -> int:
    """Insert a new observation; returns the new row id."""
    now = datetime.now(timezone.utc)
    row = await conn.fetchrow(
        """
        INSERT INTO observations
            (ticker, date, title, body, sentiment, tags,
             linked_chart_id, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
        RETURNING id
        """,
        ticker, date, title, body, sentiment, json.dumps(tags),
        linked_chart_id, now,
    )
    return row["id"]


async def update_observation(
    conn: asyncpg.Connection,
    obs_id: int,
    updates: dict,
) -> bool:
    """
    Patch an observation. ``updates`` is a dict of {column: value} pairs
    containing only the fields the caller wants to change.  ``updated_at``
    is always set to ``now()``.  Returns True if the row exists and was
    updated, False otherwise.
    """
    if not updates:
        return await _observation_exists(conn, obs_id)

    updates = {**updates, "updated_at": datetime.now(timezone.utc)}
    set_parts = [f"{k} = ${i + 1}" for i, k in enumerate(updates)]
    values = list(updates.values()) + [obs_id]
    result = await conn.execute(
        f"UPDATE observations SET {', '.join(set_parts)} "
        f"WHERE id = ${len(values)}",
        *values,
    )
    # asyncpg returns "UPDATE <n>"; non-zero means at least one row updated.
    return not result.endswith(" 0")


async def delete_observation(
    conn: asyncpg.Connection,
    obs_id: int,
) -> bool:
    """Delete an observation by id.  Returns True if a row was deleted."""
    result = await conn.execute("DELETE FROM observations WHERE id = $1", obs_id)
    return not result.endswith(" 0")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

async def _observation_exists(conn: asyncpg.Connection, obs_id: int) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM observations WHERE id = $1", obs_id)
    return row is not None
