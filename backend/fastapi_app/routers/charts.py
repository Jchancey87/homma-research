"""
fastapi_app/routers/charts.py
Async port of backend/routes/charts.py.

Handles chart image upload, listing, CRUD, and Gemini annotation import.
File I/O (save/delete) is performed via asyncio.to_thread() to stay non-blocking.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date as date_type
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..chart_service_shim import VALID_TAGS, save_chart_image, validate_tags
from ..db import get_db, row_to_dict, rows_to_list

import asyncio
from pydantic import BaseModel
from typing import Any


class ChartUpdateBody(BaseModel):
    notes: Optional[str] = None
    cleanliness_score: Optional[int] = None
    setup_type: Optional[str] = None
    timeframe: Optional[str] = None
    tags: Optional[list[str]] = None


class GeminiImportJsonBody(BaseModel):
    analysis_text: str = ""

log = logging.getLogger(__name__)
router = APIRouter(prefix="/charts", tags=["charts"])


# ---------------------------------------------------------------------------
# Internal helper — sync tag-sync (called inside a transaction)
# ---------------------------------------------------------------------------

async def _sync_chart_tags(conn: asyncpg.Connection, chart_id: int, tags: list[str]) -> None:
    """Replace all chart_tags rows for chart_id with the new tag list."""
    await conn.execute("DELETE FROM chart_tags WHERE chart_id = $1", chart_id)
    for tag in tags:
        tag = str(tag).strip()
        if tag:
            await conn.execute(
                "INSERT INTO chart_tags (chart_id, tag) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                chart_id,
                tag,
            )


# ---------------------------------------------------------------------------
# POST /charts — multipart upload
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def upload_chart(
    image: UploadFile = File(...),
    ticker: str = Form(...),
    capture_date: str = Form(...),
    timeframe: Optional[str] = Form(None),
    setup_type: Optional[str] = Form(None),
    cleanliness_score: Optional[int] = Form(None),
    notes: str = Form(""),
    tags: str = Form("[]"),  # JSON-encoded list
    db: asyncpg.Connection = Depends(get_db),
):
    """Upload a chart image and persist metadata."""
    # Parse and validate tags
    try:
        tag_list: list[str] = json.loads(tags)
        if not isinstance(tag_list, list):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="tags must be a JSON array string")

    tag_list = [str(t).strip() for t in tag_list if str(t).strip()]
    invalid = validate_tags(tag_list)
    if invalid:
        raise HTTPException(
            status_code=422,
            detail={"error": f"Invalid tags: {invalid}", "valid_tags": VALID_TAGS},
        )

    # Parse capture_date
    try:
        from datetime import date
        parsed_date = date.fromisoformat(capture_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="capture_date must be YYYY-MM-DD")

    # Save image (async-safe via shim)
    try:
        image_path = await save_chart_image(image, ticker.upper().strip(), parsed_date.isoformat())
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc))

    row = await db.fetchrow(
        """INSERT INTO chart_captures
           (ticker, capture_date, timeframe, image_path, setup_type,
            cleanliness_score, tags, notes)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           RETURNING id""",
        ticker.upper().strip(),
        parsed_date.isoformat(),
        timeframe,
        image_path,
        setup_type,
        cleanliness_score,
        json.dumps(tag_list),
        notes,
    )
    chart_id = row["id"]
    await _sync_chart_tags(db, chart_id, tag_list)

    return {"id": chart_id, "image_path": image_path}


# ---------------------------------------------------------------------------
# GET /charts — filtered list
# ---------------------------------------------------------------------------

@router.get("")
async def list_charts(
    ticker: Optional[str] = None,
    setup_type: Optional[str] = None,
    tag: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_cleanliness: Optional[int] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    """List chart captures with optional filters."""
    conditions: list[str] = []
    params: list = []

    if tag:
        # JOIN handled via subquery to keep DISTINCT logic simple
        conditions.append(
            f"cc.id IN (SELECT chart_id FROM chart_tags WHERE tag = ${len(params)+1})"
        )
        params.append(tag)

    if ticker:
        conditions.append(f"cc.ticker = ${len(params)+1}")
        params.append(ticker.upper().strip())
    if setup_type:
        conditions.append(f"cc.setup_type = ${len(params)+1}")
        params.append(setup_type)
    if date_from:
        conditions.append(f"cc.capture_date >= ${len(params)+1}")
        params.append(date_from)
    if date_to:
        conditions.append(f"cc.capture_date <= ${len(params)+1}")
        params.append(date_to)
    if min_cleanliness is not None:
        conditions.append(f"cc.cleanliness_score >= ${len(params)+1}")
        params.append(min_cleanliness)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await db.fetch(
        f"SELECT cc.* FROM chart_captures cc {where} "
        "ORDER BY cc.capture_date DESC, cc.created_at DESC",
        *params,
    )
    return rows_to_list(rows)


# ---------------------------------------------------------------------------
# GET /charts/{chart_id}
# ---------------------------------------------------------------------------

@router.get("/{chart_id}")
async def get_chart(chart_id: int, db: asyncpg.Connection = Depends(get_db)):
    row = await db.fetchrow("SELECT * FROM chart_captures WHERE id = $1", chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row_to_dict(row)


# ---------------------------------------------------------------------------
# PUT /charts/{chart_id}
# ---------------------------------------------------------------------------

@router.put("/{chart_id}")
async def update_chart(
    chart_id: int,
    body: ChartUpdateBody,
    db: asyncpg.Connection = Depends(get_db),
):
    """Partial update — accepts notes, cleanliness_score, setup_type, timeframe, tags."""
    updates: dict = {}

    if body.notes is not None:
        updates["notes"] = body.notes
    if body.cleanliness_score is not None:
        updates["cleanliness_score"] = body.cleanliness_score
    if body.setup_type is not None:
        updates["setup_type"] = body.setup_type
    if body.timeframe is not None:
        updates["timeframe"] = body.timeframe

    tag_list: list[str] | None = None
    if body.tags is not None:
        tag_list = [str(t).strip() for t in body.tags if str(t).strip()]
        invalid = validate_tags(tag_list)
        if invalid:
            raise HTTPException(
                status_code=422,
                detail={"error": f"Invalid tags: {invalid}", "valid_tags": VALID_TAGS},
            )
        updates["tags"] = json.dumps(tag_list)

    if not updates and tag_list is None:
        raise HTTPException(status_code=422, detail="No valid fields to update")

    # Build SET clause with positional params ($1, $2…)
    set_parts = [f"{k} = ${i+1}" for i, k in enumerate(updates)]
    values = list(updates.values()) + [chart_id]
    set_clause = ", ".join(set_parts)

    await db.execute(
        f"UPDATE chart_captures SET {set_clause} WHERE id = ${len(values)}",
        *values,
    )
    if tag_list is not None:
        await _sync_chart_tags(db, chart_id, tag_list)

    return {"success": True}


# ---------------------------------------------------------------------------
# DELETE /charts/{chart_id}
# ---------------------------------------------------------------------------

@router.delete("/{chart_id}")
async def delete_chart(chart_id: int, db: asyncpg.Connection = Depends(get_db)):
    row = await db.fetchrow(
        "SELECT image_path, gemini_image_path FROM chart_captures WHERE id = $1", chart_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    # Delete image files off-thread
    for path_field in ("image_path", "gemini_image_path"):
        p = row[path_field]
        if p and os.path.exists(p):
            try:
                await asyncio.to_thread(os.remove, p)
            except OSError:
                pass

    # chart_tags deleted by CASCADE
    await db.execute("DELETE FROM chart_captures WHERE id = $1", chart_id)
    return {"success": True}


# ---------------------------------------------------------------------------
# POST /charts/{chart_id}/gemini-import
# ---------------------------------------------------------------------------

@router.post("/{chart_id}/gemini-import")
async def gemini_import(
    chart_id: int,
    analysis_text: str = Form(""),
    annotated_image: Optional[UploadFile] = File(None),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Store Gemini annotation text and optional annotated image for a chart.
    Accepts either multipart/form-data or JSON (see JSON variant below).
    """
    row = await db.fetchrow(
        "SELECT ticker, capture_date FROM chart_captures WHERE id = $1", chart_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    ticker = row["ticker"]
    capture_date = str(row["capture_date"])

    image_path: str | None = None
    if annotated_image and annotated_image.filename:
        try:
            image_path = await save_chart_image(
                annotated_image, ticker=ticker, capture_date=capture_date, subfolder="annotated"
            )
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc))

    analysis_text = (analysis_text or "").strip()

    if image_path:
        await db.execute(
            """UPDATE chart_captures
               SET gemini_annotation = $1,
                   llm_annotation    = $1,
                   gemini_image_path = $2,
                   gemini_imported_at = NOW()
               WHERE id = $3""",
            analysis_text, image_path, chart_id,
        )
    else:
        await db.execute(
            """UPDATE chart_captures
               SET gemini_annotation = $1,
                   llm_annotation    = $1,
                   gemini_imported_at = NOW()
               WHERE id = $2""",
            analysis_text, chart_id,
        )

    return {"success": True, "gemini_image_path": image_path, "analysis_text": analysis_text}


# ---------------------------------------------------------------------------
# POST /charts/{chart_id}/gemini-import — JSON variant
# ---------------------------------------------------------------------------

@router.post("/{chart_id}/gemini-import-json")
async def gemini_import_json(
    chart_id: int,
    body: GeminiImportJsonBody,
    db: asyncpg.Connection = Depends(get_db),
):
    """JSON-body variant of gemini-import (no file upload)."""
    row = await db.fetchrow(
        "SELECT id FROM chart_captures WHERE id = $1", chart_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    analysis_text = (body.analysis_text or "").strip()
    await db.execute(
        """UPDATE chart_captures
           SET gemini_annotation   = $1,
               llm_annotation      = $1,
               gemini_imported_at  = NOW()
           WHERE id = $2""",
        analysis_text, chart_id,
    )
    return {"success": True, "analysis_text": analysis_text}
