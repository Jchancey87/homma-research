"""
fastapi_app/routers/continuation.py
Async port of backend/routes/continuation_picks.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from ..db import get_db, rows_to_list, row_to_dict
from validation.schemas import PickAddBody

log = logging.getLogger(__name__)
router = APIRouter(prefix="/continuation-picks", tags=["continuation"])


class DeactivateBody(BaseModel):
    reason: str = "manually dismissed"


@router.get("")
async def list_picks(
    include_inactive: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    db: asyncpg.Connection = Depends(get_db),
):
    import asyncio
    
    if include_inactive:
        rows = await db.fetch(
            """SELECT * FROM continuation_picks
               ORDER BY is_active DESC, date DESC, rank ASC
               LIMIT $1""",
            limit,
        )
    else:
        rows = await db.fetch(
            """SELECT * FROM continuation_picks
               WHERE is_active = TRUE
               ORDER BY date DESC, rank ASC
               LIMIT $1""",
            limit,
        )
    
    results = rows_to_list(rows)
    if not results:
        return results
        
    tickers = {r["ticker"] for r in results}
    try:
        from momentum_screener.schwab.http_client import get_quotes
        quotes = await asyncio.to_thread(get_quotes, list(tickers))
    except Exception as e:
        log.warning(f"Failed to fetch live quotes for continuation picks: {e}")
        quotes = {}
        
    for r in results:
        ticker = r["ticker"]
        q_data = quotes.get(ticker, {}) if quotes else {}
        quote = q_data.get('quote', {}) if q_data else {}
        
        r["today_last"] = quote.get("lastPrice")
        r["today_open"] = quote.get("openPrice")
        r["today_volume"] = quote.get("totalVolume")
        r["today_change_pct"] = quote.get("netPercentChange")
        
    return results


@router.post("", status_code=201)
async def add_picks(data: PickAddBody, db: asyncpg.Connection = Depends(get_db)):
    """Batch-insert continuation picks (idempotent via ON CONFLICT DO NOTHING)."""
    now = datetime.now(timezone.utc)
    inserted = 0
    for p in data.picks:
        await db.execute(
            """INSERT INTO continuation_picks
               (ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (ticker, date) DO NOTHING""",
            p.ticker, p.date.isoformat(), p.reason, p.gap_pct,
            p.float_shares, p.rvol_15m, p.sector, p.rank, now,
        )
        inserted += 1
    return {"inserted": inserted}


@router.post("/{pick_id}/deactivate")
async def deactivate_pick(
    pick_id: int,
    body: DeactivateBody = Body(default_factory=DeactivateBody),
    db: asyncpg.Connection = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    row = await db.fetchrow("SELECT id FROM continuation_picks WHERE id = $1", pick_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await db.execute(
        """UPDATE continuation_picks
           SET is_active = FALSE, deactivated_at = $1, deactivated_reason = $2
           WHERE id = $3""",
        now, body.reason, pick_id,
    )
    return {"success": True}


@router.delete("/{pick_id}")
async def delete_pick(pick_id: int, db: asyncpg.Connection = Depends(get_db)):
    row = await db.fetchrow("SELECT id FROM continuation_picks WHERE id = $1", pick_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await db.execute("DELETE FROM continuation_picks WHERE id = $1", pick_id)
    return {"success": True}


@router.get("/stats")
async def picks_stats(db: asyncpg.Connection = Depends(get_db)):
    rows = await db.fetch(
        """SELECT date, COUNT(*) AS count
           FROM continuation_picks
           WHERE is_active = TRUE
           GROUP BY date
           ORDER BY date DESC
           LIMIT 14"""
    )
    return rows_to_list(rows)
