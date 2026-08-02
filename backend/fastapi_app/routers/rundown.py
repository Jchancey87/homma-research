"""
fastapi_app/routers/rundown.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
API endpoints for the Daily Market Rundown workflow.
Thin router following RFC-001/RFC-005 conventions:
- No raw SQL inside endpoints.
- Business logic is delegated to services/rundown_service.py.
"""
from __future__ import annotations

import logging
from datetime import date as date_cls
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..db import get_db
from ..db import rundown as db_rundown
from services import rundown_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/rundown", tags=["rundown"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class RundownGenerateRequest(BaseModel):
    date: Optional[date_cls] = None
    raw_email_text: Optional[str] = None
    force_refresh: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", status_code=200)
@router.get("/today", status_code=200)
async def get_today_rundown(
    date: Optional[date_cls] = Query(None, description="Target date (YYYY-MM-DD), defaults to today ET"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get the cached Daily Market Rundown for the specified date (or today).
    If no rundown has been generated yet for the date, triggers on-demand generation.
    """
    return await rundown_service.get_or_generate_rundown(db, target_date=date)


@router.post("/generate", status_code=201)
async def generate_rundown(
    body: RundownGenerateRequest,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Generate or refresh a Daily Market Rundown.
    Optionally accepts raw morning research email text to extract & synthesize key info.
    """
    return await rundown_service.get_or_generate_rundown(
        db,
        target_date=body.date,
        raw_email_text=body.raw_email_text,
        force_refresh=body.force_refresh,
    )


@router.get("/history", status_code=200)
async def list_recent_rundowns(
    limit: int = Query(10, ge=1, le=50),
    db: asyncpg.Connection = Depends(get_db),
):
    """List recent daily market rundowns."""
    return await db_rundown.list_recent_rundowns(db, limit=limit)
