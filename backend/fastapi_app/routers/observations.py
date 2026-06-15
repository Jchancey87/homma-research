"""
fastapi_app/routers/observations.py
Async port of backend/routes/observations.py.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_db
from ..db import observations as db_observations
from validation import normalize_ticker
from validation.schemas import ObservationCreateBody, ObservationUpdateBody

log = logging.getLogger(__name__)
router = APIRouter(prefix="/observations", tags=["observations"])


@router.get("")
async def list_observations(
    ticker:    Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    tag:       Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
    limit:     int          = Query(100, ge=1, le=500),
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db_observations.list_observations(
        db,
        ticker=normalize_ticker(ticker) if ticker else None,
        sentiment=sentiment,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return rows


@router.get("/{ticker}")
async def get_observations_for_ticker(
    ticker: str,
    db: asyncpg.Connection = Depends(get_db),
):
    return await db_observations.list_observations_for_ticker(
        db, normalize_ticker(ticker)
    )


@router.post("", status_code=201)
async def create_observation(
    data: ObservationCreateBody,
    db: asyncpg.Connection = Depends(get_db),
):
    obs_id = await db_observations.create_observation(
        db,
        ticker=data.ticker,
        date=data.date.isoformat(),
        title=data.title,
        body=data.body,
        sentiment=data.sentiment,
        tags=data.tags,
        linked_chart_id=data.linked_chart_id,
    )
    return {"id": obs_id}


@router.put("/{obs_id}")
async def update_observation(
    obs_id: int,
    data: ObservationUpdateBody,
    db: asyncpg.Connection = Depends(get_db),
):
    existing = await db_observations.get_observation_by_id(db, obs_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")

    updates: dict = {}
    if data.title is not None:
        updates["title"] = data.title
    if data.body is not None:
        updates["body"] = data.body
    if data.sentiment is not None:
        updates["sentiment"] = data.sentiment
    if data.tags is not None:
        updates["tags"] = json.dumps(data.tags)
    if data.date is not None:
        updates["date"] = data.date.isoformat()
    if data.linked_chart_id is not None:
        updates["linked_chart_id"] = data.linked_chart_id

    await db_observations.update_observation(db, obs_id, updates)
    return {"success": True}


@router.delete("/{obs_id}")
async def delete_observation(
    obs_id: int,
    db: asyncpg.Connection = Depends(get_db),
):
    deleted = await db_observations.delete_observation(db, obs_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True}
