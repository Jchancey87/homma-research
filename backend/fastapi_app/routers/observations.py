"""
fastapi_app/routers/observations.py
Async port of backend/routes/observations.py.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_db, rows_to_list, row_to_dict
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
    limit:     int           = Query(100, ge=1, le=500),
    db: asyncpg.Connection = Depends(get_db),
):
    conditions: list[str] = []
    params: list = []

    if ticker:
        conditions.append(f"ticker = ${len(params)+1}")
        params.append(ticker.upper().strip())
    if sentiment:
        conditions.append(f"sentiment = ${len(params)+1}")
        params.append(sentiment)
    if tag:
        conditions.append(f"tags ILIKE ${len(params)+1}")
        params.append(f"%{tag}%")
    if date_from:
        conditions.append(f"date >= ${len(params)+1}")
        params.append(date_from)
    if date_to:
        conditions.append(f"date <= ${len(params)+1}")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)
    rows = await db.fetch(
        f"SELECT * FROM observations {where} ORDER BY date DESC, created_at DESC LIMIT ${len(params)}",
        *params,
    )
    return rows_to_list(rows)


@router.get("/{ticker}")
async def get_observations_for_ticker(ticker: str, db: asyncpg.Connection = Depends(get_db)):
    ticker = ticker.upper().strip()
    rows = await db.fetch(
        "SELECT * FROM observations WHERE ticker = $1 ORDER BY date DESC, created_at DESC",
        ticker,
    )
    return rows_to_list(rows)


@router.post("", status_code=201)
async def create_observation(data: ObservationCreateBody, db: asyncpg.Connection = Depends(get_db)):
    tags = json.dumps(data.tags)
    now  = datetime.now(timezone.utc)
    row = await db.fetchrow(
        """INSERT INTO observations
           (ticker, date, title, body, sentiment, tags, linked_chart_id, created_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8)
           RETURNING id""",
        data.ticker, data.date.isoformat(), data.title, data.body,
        data.sentiment, tags, data.linked_chart_id, now,
    )
    return {"id": row["id"]}


@router.put("/{obs_id}")
async def update_observation(
    obs_id: int, data: ObservationUpdateBody, db: asyncpg.Connection = Depends(get_db)
):
    row = await db.fetchrow("SELECT id FROM observations WHERE id = $1", obs_id)
    if not row:
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
    updates["updated_at"] = datetime.now(timezone.utc)

    set_parts = [f"{k} = ${i+1}" for i, k in enumerate(updates)]
    values    = list(updates.values()) + [obs_id]
    await db.execute(
        f"UPDATE observations SET {', '.join(set_parts)} WHERE id = ${len(values)}",
        *values,
    )
    return {"success": True}


@router.delete("/{obs_id}")
async def delete_observation(obs_id: int, db: asyncpg.Connection = Depends(get_db)):
    row = await db.fetchrow("SELECT id FROM observations WHERE id = $1", obs_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await db.execute("DELETE FROM observations WHERE id = $1", obs_id)
    return {"success": True}
