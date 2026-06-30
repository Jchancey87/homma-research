"""
fastapi_app/db/rss.py
~~~~~~~~~~~~~~~~~~~~~
Read/write helpers for RSS feed tables.
Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain
dicts/lists/booleans.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# RSS Sources
# ---------------------------------------------------------------------------

async def list_rss_sources(conn: asyncpg.Connection) -> list[dict]:
    """Fetch all RSS sources."""
    rows = await conn.fetch("SELECT * FROM rss_sources ORDER BY name")
    return [dict(r) for r in rows]


async def insert_rss_source(
    conn: asyncpg.Connection,
    name: str,
    feed_url: str,
    category: str,
    is_active: bool = True,
) -> int:
    """Insert a new RSS source, returning its ID."""
    row = await conn.fetchrow(
        "INSERT INTO rss_sources (name, feed_url, category, is_active) "
        "VALUES ($1, $2, $3, $4) RETURNING id",
        name, feed_url, category, is_active
    )
    return row["id"]


async def update_rss_source(
    conn: asyncpg.Connection,
    source_id: int,
    updates: dict,
) -> bool:
    """Patch an RSS source row. Returns True if a row was updated."""
    if not updates:
        return True
    set_parts = [f"{k} = ${i + 1}" for i, k in enumerate(updates)]
    values = list(updates.values()) + [source_id]
    result = await conn.execute(
        f"UPDATE rss_sources SET {', '.join(set_parts)} "
        f"WHERE id = ${len(values)}",
        *values,
    )
    return not result.endswith(" 0")


async def delete_rss_source(conn: asyncpg.Connection, source_id: int) -> bool:
    """Delete an RSS source. Returns True if deleted."""
    result = await conn.execute("DELETE FROM rss_sources WHERE id = $1", source_id)
    return not result.endswith(" 0")


# ---------------------------------------------------------------------------
# RSS Feed Pool (Raw Ingested)
# ---------------------------------------------------------------------------

async def list_rss_feed_pool(
    conn: asyncpg.Connection,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List raw ingested feed items from pool, ordered by published_at DESC."""
    if status:
        rows = await conn.fetch(
            "SELECT * FROM rss_feed_pool WHERE status = $1 "
            "ORDER BY published_at DESC LIMIT $2",
            status, limit
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM rss_feed_pool "
            "ORDER BY published_at DESC LIMIT $1",
            limit
        )
    return [dict(r) for r in rows]


async def get_rss_feed_pool_item(conn: asyncpg.Connection, item_id: int) -> Optional[dict]:
    """Fetch a single feed pool item by ID."""
    row = await conn.fetchrow("SELECT * FROM rss_feed_pool WHERE id = $1", item_id)
    return dict(row) if row else None


async def insert_rss_feed_pool_item(
    conn: asyncpg.Connection,
    source_id: int,
    guid: str,
    title: str,
    description: Optional[str],
    link: str,
    published_at: datetime,
    detected_tickers: list[str],
    sector: Optional[str] = None,
    status: str = "pending",
) -> bool:
    """Insert a raw feed item. ON CONFLICT DO NOTHING. Returns True if inserted."""
    result = await conn.execute(
        "INSERT INTO rss_feed_pool (source_id, guid, title, description, link, published_at, detected_tickers, sector, status) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
        "ON CONFLICT (guid) DO NOTHING",
        source_id, guid, title, description, link, published_at, detected_tickers, sector, status
    )
    return not result.endswith(" 0")


async def update_rss_feed_pool_status(
    conn: asyncpg.Connection,
    item_id: int,
    status: str,
) -> bool:
    """Update staging status (approved/rejected)."""
    result = await conn.execute(
        "UPDATE rss_feed_pool SET status = $1 WHERE id = $2",
        status, item_id
    )
    return not result.endswith(" 0")


# ---------------------------------------------------------------------------
# Curated RSS Items
# ---------------------------------------------------------------------------

async def list_curated_rss_items(
    conn: asyncpg.Connection,
    limit: int = 50,
) -> list[dict]:
    """List curated/published feed items, ordered by published_at DESC."""
    rows = await conn.fetch(
        "SELECT * FROM curated_rss_items "
        "ORDER BY published_at DESC LIMIT $1",
        limit
    )
    return [dict(r) for r in rows]


async def insert_curated_rss_item(
    conn: asyncpg.Connection,
    pool_item_id: Optional[int],
    guid: str,
    title: str,
    description: str,
    link: str,
    published_at: datetime,
    curated_by: Optional[str],
    associated_tickers: list[str],
    curated_notes: Optional[str] = None,
) -> bool:
    """Insert a curated RSS item, publishing it. Returns True on success."""
    result = await conn.execute(
        "INSERT INTO curated_rss_items (pool_item_id, guid, title, description, link, published_at, curated_by, associated_tickers, curated_notes) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
        "ON CONFLICT (guid) DO UPDATE SET "
        "title = EXCLUDED.title, description = EXCLUDED.description, "
        "associated_tickers = EXCLUDED.associated_tickers, curated_notes = EXCLUDED.curated_notes",
        pool_item_id, guid, title, description, link, published_at, curated_by, associated_tickers, curated_notes
    )
    return not result.endswith(" 0")


async def get_unsent_telegram_curated_items(conn: asyncpg.Connection) -> list[dict]:
    """Get curated articles that have not been sent to Telegram yet."""
    rows = await conn.fetch(
        "SELECT * FROM curated_rss_items WHERE telegram_sent = FALSE ORDER BY published_at ASC"
    )
    return [dict(r) for r in rows]


async def mark_telegram_sent(conn: asyncpg.Connection, item_id: int) -> bool:
    """Flag that a curated item was successfully notified on Telegram."""
    result = await conn.execute(
        "UPDATE curated_rss_items SET telegram_sent = TRUE WHERE id = $1",
        item_id
    )
    return not result.endswith(" 0")
