"""
fastapi_app/db/charts.py
~~~~~~~~~~~~~~~~~~~~~~~~
Read/write helpers for the ``chart_captures`` and ``chart_tags`` tables.

Tables:
  - chart_captures  — one row per uploaded chart image
  - chart_tags      — many-to-many junction of (chart_id, tag) for normalized
                      tag filtering (replaces the legacy ``chart_captures.tags``
                      JSON-string column).

Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain dicts/ints/
booleans so routers stay Router-Layer-Rules compliant.
"""
from __future__ import annotations

import json
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# chart_captures — writes
# ---------------------------------------------------------------------------

async def insert_chart_capture(
    conn: asyncpg.Connection,
    *,
    ticker: str,
    capture_date: str,        # YYYY-MM-DD
    image_path: str,
    timeframe: Optional[str] = None,
    setup_type: Optional[str] = None,
    cleanliness_score: Optional[int] = None,
    tags_json: str = "[]",
    notes: str = "",
) -> int:
    """Insert a new chart_captures row; returns the new id."""
    row = await conn.fetchrow(
        """
        INSERT INTO chart_captures
            (ticker, capture_date, timeframe, image_path, setup_type,
             cleanliness_score, tags, notes)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        ticker, capture_date, timeframe, image_path, setup_type,
        cleanliness_score, tags_json, notes,
    )
    return row["id"]


async def update_chart_capture(
    conn: asyncpg.Connection,
    chart_id: int,
    updates: dict,
) -> bool:
    """
    Patch a chart_captures row.  ``updates`` is a dict of {column: value}
    pairs containing only fields the caller wants to change.  Returns True
    if a row was updated, False otherwise.
    """
    if not updates:
        return await _chart_capture_exists(conn, chart_id)

    set_parts = [f"{k} = ${i + 1}" for i, k in enumerate(updates)]
    values = list(updates.values()) + [chart_id]
    result = await conn.execute(
        f"UPDATE chart_captures SET {', '.join(set_parts)} "
        f"WHERE id = ${len(values)}",
        *values,
    )
    return not result.endswith(" 0")


async def update_gemini_import(
    conn: asyncpg.Connection,
    chart_id: int,
    analysis_text: str,
    image_path: Optional[str] = None,
) -> None:
    """
    Set Gemini annotation text (also mirrored to ``llm_annotation``) and
    optionally the annotated image path.  ``gemini_imported_at`` is
    always updated to ``NOW()``.
    """
    if image_path:
        await conn.execute(
            """
            UPDATE chart_captures
            SET gemini_annotation   = $1,
                llm_annotation      = $1,
                gemini_image_path   = $2,
                gemini_imported_at  = NOW()
            WHERE id = $3
            """,
            analysis_text, image_path, chart_id,
        )
    else:
        await conn.execute(
            """
            UPDATE chart_captures
            SET gemini_annotation   = $1,
                llm_annotation      = $1,
                gemini_imported_at  = NOW()
            WHERE id = $2
            """,
            analysis_text, chart_id,
        )


async def delete_chart_capture(
    conn: asyncpg.Connection,
    chart_id: int,
) -> bool:
    """Delete a chart_captures row (CASCADE removes chart_tags rows)."""
    result = await conn.execute("DELETE FROM chart_captures WHERE id = $1", chart_id)
    return not result.endswith(" 0")


# ---------------------------------------------------------------------------
# chart_captures — reads
# ---------------------------------------------------------------------------

async def list_chart_captures(
    conn: asyncpg.Connection,
    *,
    ticker: Optional[str] = None,
    setup_type: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_cleanliness: Optional[int] = None,
) -> list[dict]:
    """List chart_captures matching the optional filters, newest first."""
    conditions: list[str] = []
    params: list = []

    if tag:
        # Subquery keeps the chart_captures table alias short.
        conditions.append(
            f"cc.id IN (SELECT chart_id FROM chart_tags WHERE tag = ${len(params) + 1})"
        )
        params.append(tag)
    if ticker:
        conditions.append(f"cc.ticker = ${len(params) + 1}")
        params.append(ticker)
    if setup_type:
        conditions.append(f"cc.setup_type = ${len(params) + 1}")
        params.append(setup_type)
    if date_from:
        conditions.append(f"cc.capture_date >= ${len(params) + 1}")
        params.append(date_from)
    if date_to:
        conditions.append(f"cc.capture_date <= ${len(params) + 1}")
        params.append(date_to)
    if min_cleanliness is not None:
        conditions.append(f"cc.cleanliness_score >= ${len(params) + 1}")
        params.append(min_cleanliness)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await conn.fetch(
        f"SELECT cc.* FROM chart_captures cc {where} "
        f"ORDER BY cc.capture_date DESC, cc.created_at DESC",
        *params,
    )
    return [dict(r) for r in rows]


async def get_chart_capture(
    conn: asyncpg.Connection,
    chart_id: int,
) -> dict | None:
    """Fetch a single chart_captures row by id, or None."""
    row = await conn.fetchrow(
        "SELECT * FROM chart_captures WHERE id = $1", chart_id
    )
    return dict(row) if row else None


async def get_chart_capture_paths(
    conn: asyncpg.Connection,
    chart_id: int,
) -> dict | None:
    """Return the on-disk paths needed for chart deletion cleanup."""
    row = await conn.fetchrow(
        "SELECT image_path, gemini_image_path FROM chart_captures WHERE id = $1",
        chart_id,
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# chart_tags — normalised junction table
# ---------------------------------------------------------------------------

async def sync_chart_tags(
    conn: asyncpg.Connection,
    chart_id: int,
    tags: list[str],
) -> None:
    """
    Replace the set of chart_tags rows for ``chart_id`` with ``tags``.
    Whitespace-only entries are dropped.  Duplicates collapse via the
    (chart_id, tag) primary key.
    """
    await conn.execute("DELETE FROM chart_tags WHERE chart_id = $1", chart_id)
    for tag in tags:
        clean = str(tag).strip()
        if not clean:
            continue
        await conn.execute(
            "INSERT INTO chart_tags (chart_id, tag) "
            "VALUES ($1, $2) ON CONFLICT DO NOTHING",
            chart_id, clean,
        )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

async def _chart_capture_exists(conn: asyncpg.Connection, chart_id: int) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM chart_captures WHERE id = $1", chart_id)
    return row is not None
