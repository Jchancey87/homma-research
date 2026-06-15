"""
fastapi_app/routers/charts.py
Async port of backend/routes/charts.py.

Handles chart image upload, listing, CRUD, and Gemini annotation import.
File I/O (save/delete) is performed via asyncio.to_thread() to stay non-blocking.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..db import get_db
from ..db import charts as db_charts
from services.chart_service import VALID_TAGS, save_chart_image, validate_tags
from validation import normalize_ticker


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
        parsed_date = date.fromisoformat(capture_date)
    except ValueError:
        raise HTTPException(status_code=422, detail="capture_date must be YYYY-MM-DD")

    ticker_norm = normalize_ticker(ticker)

    # Save image — adapt FastAPI UploadFile to framework-agnostic (bytes, content_type, filename)
    try:
        blob = await image.read()
        image_path = await asyncio.to_thread(
            save_chart_image,
            blob, image.content_type or "", image.filename or "",
            ticker=ticker_norm, capture_date=parsed_date.isoformat(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc))

    chart_id = await db_charts.insert_chart_capture(
        db,
        ticker=ticker_norm,
        capture_date=parsed_date.isoformat(),
        image_path=image_path,
        timeframe=timeframe,
        setup_type=setup_type,
        cleanliness_score=cleanliness_score,
        tags_json=json.dumps(tag_list),
        notes=notes,
    )
    await db_charts.sync_chart_tags(db, chart_id, tag_list)

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
    return await db_charts.list_chart_captures(
        db,
        ticker=normalize_ticker(ticker) if ticker else None,
        setup_type=setup_type,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
        min_cleanliness=min_cleanliness,
    )


# ---------------------------------------------------------------------------
# GET /charts/{chart_id}
# ---------------------------------------------------------------------------

@router.get("/{chart_id}")
async def get_chart(chart_id: int, db: asyncpg.Connection = Depends(get_db)):
    row = await db_charts.get_chart_capture(db, chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


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

    tag_list: Optional[list[str]] = None
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

    await db_charts.update_chart_capture(db, chart_id, updates)
    if tag_list is not None:
        await db_charts.sync_chart_tags(db, chart_id, tag_list)

    return {"success": True}


# ---------------------------------------------------------------------------
# DELETE /charts/{chart_id}
# ---------------------------------------------------------------------------

@router.delete("/{chart_id}")
async def delete_chart(chart_id: int, db: asyncpg.Connection = Depends(get_db)):
    row = await db_charts.get_chart_capture_paths(db, chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    # Delete image files off-thread
    for path_field in ("image_path", "gemini_image_path"):
        p = row.get(path_field)
        if p and os.path.exists(p):
            try:
                await asyncio.to_thread(os.remove, p)
            except OSError:
                pass

    # chart_tags deleted by CASCADE
    await db_charts.delete_chart_capture(db, chart_id)
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
    Accepts multipart/form-data.
    """
    row = await db_charts.get_chart_capture(db, chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    ticker = row["ticker"]
    capture_date = str(row["capture_date"])

    image_path: Optional[str] = None
    if annotated_image and annotated_image.filename:
        try:
            blob = await annotated_image.read()
            image_path = await asyncio.to_thread(
                save_chart_image,
                blob, annotated_image.content_type or "", annotated_image.filename or "",
                ticker=ticker, capture_date=capture_date, subfolder="annotated",
            )
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc))

    analysis_text = (analysis_text or "").strip()
    await db_charts.update_gemini_import(db, chart_id, analysis_text, image_path)

    return {
        "success": True,
        "gemini_image_path": image_path,
        "analysis_text": analysis_text,
    }


# ---------------------------------------------------------------------------
# POST /charts/{chart_id}/gemini-import-json
# ---------------------------------------------------------------------------

@router.post("/{chart_id}/gemini-import-json")
async def gemini_import_json(
    chart_id: int,
    body: GeminiImportJsonBody,
    db: asyncpg.Connection = Depends(get_db),
):
    """JSON-body variant of gemini-import (no file upload)."""
    row = await db_charts.get_chart_capture(db, chart_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    analysis_text = (body.analysis_text or "").strip()
    await db_charts.update_gemini_import(db, chart_id, analysis_text)
    return {"success": True, "analysis_text": analysis_text}
