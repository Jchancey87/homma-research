"""
fastapi_app/routers/continuation.py
Async port of backend/routes/continuation_picks.py.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from ..db import get_db
from ..db import continuation_picks as db_continuation_picks
from services.continuation_analytics import compute_performance_stats
from services.live_quotes_service import get_live_quotes
from validation.schemas import PickAddBody

log = logging.getLogger(__name__)
router = APIRouter(prefix="/continuation-picks", tags=["continuation"])


class DeactivateBody(BaseModel):
    reason: str = "manually dismissed"


def _clean_nans(obj):
    """Recursively convert float NaN/Inf values to None for JSON compliance."""
    if isinstance(obj, dict):
        return {k: _clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_nans(x) for x in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


@router.get("")
async def list_picks(
    include_inactive: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    db: asyncpg.Connection = Depends(get_db),
):
    rows = await db_continuation_picks.list_picks(
        db, include_inactive=include_inactive, limit=limit
    )
    if not rows:
        return rows

    tickers = [r["ticker"] for r in rows]
    quotes = await get_live_quotes(tickers)

    for r in rows:
        nq = quotes.get(r["ticker"])
        r["today_last"] = nq.last_price if nq else None
        r["today_open"] = nq.open_price if nq else None
        r["today_volume"] = nq.volume if nq else None
        r["today_change_pct"] = nq.change_pct if nq else None

    return _clean_nans(rows)


@router.post("", status_code=201)
async def add_picks(data: PickAddBody, db: asyncpg.Connection = Depends(get_db)):
    """Batch-insert continuation picks (idempotent via ON CONFLICT DO NOTHING)."""
    now = datetime.now(timezone.utc)
    inserted = 0
    for p in data.picks:
        # ``inserted`` mirrors the legacy contract: it counts attempts, not
        # only rows that survived the ON CONFLICT clause.  Callers that
        # need the real success count can read the response status.
        await db_continuation_picks.insert_pick(
            db,
            ticker=p.ticker,
            date=p.date.isoformat(),
            reason=p.reason,
            gap_pct=p.gap_pct,
            float_shares=p.float_shares,
            rvol_15m=p.rvol_15m,
            sector=p.sector,
            rank=p.rank,
            created_at=now,
        )
        inserted += 1
    return {"inserted": inserted}


@router.post("/{pick_id}/deactivate")
async def deactivate_pick(
    pick_id: int,
    body: DeactivateBody = Body(default_factory=DeactivateBody),
    db: asyncpg.Connection = Depends(get_db),
):
    if not await db_continuation_picks.pick_exists(db, pick_id):
        raise HTTPException(status_code=404, detail="Not found")
    await db_continuation_picks.deactivate_pick(
        db, pick_id, body.reason, datetime.now(timezone.utc)
    )
    return {"success": True}


@router.delete("/{pick_id}")
async def delete_pick(pick_id: int, db: asyncpg.Connection = Depends(get_db)):
    if not await db_continuation_picks.pick_exists(db, pick_id):
        raise HTTPException(status_code=404, detail="Not found")
    await db_continuation_picks.delete_pick(db, pick_id)
    return {"success": True}


@router.get("/stats")
async def picks_stats(db: asyncpg.Connection = Depends(get_db)):
    return await db_continuation_picks.picks_stats_last_14_days(db)


@router.post("/refresh-performance")
async def refresh_performance():
    """Manually triggers performance historical tracking update."""
    from services.continuation_performance_service import update_all_continuation_performances
    count = await asyncio.to_thread(update_all_continuation_performances)
    return {"updated": count}


@router.get("/performance")
async def get_performance_stats(db: asyncpg.Connection = Depends(get_db)):
    """Computes a statistical scorecard of continuation picks performance."""
    return await compute_performance_stats(db)
