"""
fastapi_app/db/rundown.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Read/write helpers for daily_rundowns table.
Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain dicts/lists/booleans.
"""
from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

import asyncpg


async def get_daily_rundown_by_date(
    conn: asyncpg.Connection,
    target_date: date_cls,
) -> Optional[dict]:
    """Fetch stored Daily Market Rundown for a specific date."""
    row = await conn.fetchrow(
        "SELECT id, date, content, raw_source, created_at, updated_at "
        "FROM daily_rundowns WHERE date = $1",
        target_date,
    )
    return dict(row) if row else None


async def save_daily_rundown(
    conn: asyncpg.Connection,
    target_date: date_cls,
    content: str,
    raw_source: Optional[str] = None,
) -> dict:
    """Insert or update Daily Market Rundown for a date."""
    row = await conn.fetchrow(
        """
        INSERT INTO daily_rundowns (date, content, raw_source, created_at, updated_at)
        VALUES ($1, $2, $3, NOW(), NOW())
        ON CONFLICT (date) DO UPDATE SET
            content = EXCLUDED.content,
            raw_source = EXCLUDED.raw_source,
            updated_at = NOW()
        RETURNING id, date, content, raw_source, created_at, updated_at
        """,
        target_date, content, raw_source
    )
    return dict(row)


async def list_recent_rundowns(
    conn: asyncpg.Connection,
    limit: int = 10,
) -> list[dict]:
    """List recent daily rundowns ordered by date DESC."""
    rows = await conn.fetch(
        "SELECT id, date, content, created_at, updated_at "
        "FROM daily_rundowns ORDER BY date DESC LIMIT $1",
        limit
    )
    return [dict(r) for r in rows]
