import os
import asyncio
import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import asyncpg
import redis.asyncio as aioredis

from fastapi_app.db import get_db, rows_to_list
from services.alerts_analytics import compute_daily_summary, compute_performance_scorecard

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])

# Resolve Redis URL
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')

@router.get("/stream")
async def stream_alerts():
    """
    Server-Sent Events (SSE) endpoint to stream real-time screener alerts.
    Subscribes to 'screener:alerts' Redis channel and yields messages to frontend.
    """
    async def event_generator():
        logger.info("[SSE] Client connected to alerts stream")
        r = aioredis.from_url(redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe("screener:alerts")
        
        try:
            while True:
                # Non-blocking fetch of pubsub message
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    data = msg['data'].decode('utf-8')
                    yield f"data: {data}\n\n"
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("[SSE] Client disconnected from alerts stream")
        finally:
            await pubsub.unsubscribe("screener:alerts")
            await pubsub.close()
            await r.aclose()
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/history")
async def get_alerts_history(limit: int = 50, db: asyncpg.Connection = Depends(get_db)):
    """
    Retrieve historical screener alerts from PostgreSQL database.
    """
    rows = await db.fetch("""
        SELECT id, symbol, alert_time, trigger_price, trigger_volume,
               rel_vol, gap_pct, float_shares, alert_type
        FROM screener_alerts
        ORDER BY alert_time DESC
        LIMIT $1
    """, limit)
    return rows_to_list(rows)


from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException
from datetime import date as date_cls

class FeedbackBody(BaseModel):
    alert_time: str
    feedback_score: Optional[str] = None
    feedback_notes: Optional[str] = None

@router.get("/dates")
async def get_alert_dates(db: asyncpg.Connection = Depends(get_db)):
    """
    Get all unique dates that have logged alerts.
    """
    rows = await db.fetch("""
        SELECT DISTINCT (alert_time AT TIME ZONE 'America/New_York')::date AS alert_date
        FROM public.screener_alerts
        ORDER BY alert_date DESC
    """)
    return [r['alert_date'].isoformat() for r in rows if r['alert_date']]

@router.get("/daily-summary")
async def get_alerts_daily_summary(date: Optional[str] = None, db: asyncpg.Connection = Depends(get_db)):
    """
    Get all alerts for a specific date (US/Eastern), grouped by ticker symbol,
    joined with stock fundamentals. Delegates analytics to
    services.alerts_analytics.compute_daily_summary.
    """
    target_date = None
    if date:
        try:
            target_date = date_cls.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Must be YYYY-MM-DD.")
    return await compute_daily_summary(db, target_date)

@router.post("/{alert_id}/feedback")
async def save_alert_feedback(
    alert_id: int,
    body: FeedbackBody,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Update feedback rating and notes for a specific alert trigger.
    """
    try:
        from datetime import datetime
        time_str = body.alert_time.replace('Z', '+00:00')
        alert_time_dt = datetime.fromisoformat(time_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid alert_time format: {exc}. Must be ISO.")

    # Update screener_alerts
    res = await db.execute("""
        UPDATE public.screener_alerts
        SET feedback_score = $1, feedback_notes = $2
        WHERE id = $3 AND alert_time = $4
    """, body.feedback_score, body.feedback_notes, alert_id, alert_time_dt)

    # Also update archive
    await db.execute("""
        UPDATE public.screener_alerts_archive
        SET feedback_score = $1, feedback_notes = $2
        WHERE id = $3 AND alert_time = $4
    """, body.feedback_score, body.feedback_notes, alert_id, alert_time_dt)

    return {"status": "success", "updated": res}


@router.get("/performance")
async def get_alerts_performance(
    days: int = 30,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Statistical performance scorecard for screener alerts.
    Delegates the CTE+FILTER aggregation to services.alerts_analytics.
    """
    return await compute_performance_scorecard(db, days)
