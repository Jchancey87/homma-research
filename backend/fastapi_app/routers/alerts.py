import os
import asyncio
import logging
from datetime import date as date_cls, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncpg
import redis.asyncio as aioredis

from fastapi_app.db import get_db
from fastapi_app.db import screener_alerts as db_screener_alerts
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
    """Retrieve historical screener alerts from PostgreSQL database."""
    return await db_screener_alerts.list_recent_alerts(db, limit=limit)


class FeedbackBody(BaseModel):
    alert_time: str
    feedback_score: Optional[str] = None
    feedback_notes: Optional[str] = None


@router.get("/dates")
async def get_alert_dates(db: asyncpg.Connection = Depends(get_db)):
    """Get all unique dates that have logged alerts."""
    return await db_screener_alerts.list_alert_dates(db)


@router.get("/daily-summary")
async def get_alerts_daily_summary(
    date: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Get all alerts for a specific date (Eastern timezone), grouped by ticker symbol,
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
    db: asyncpg.Connection = Depends(get_db),
):
    """Update feedback rating and notes for a specific alert trigger."""
    try:
        time_str = body.alert_time.replace('Z', '+00:00')
        alert_time_dt = datetime.fromisoformat(time_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid alert_time format: {exc}. Must be ISO.")

    updated_active, updated_archive = await db_screener_alerts.save_alert_feedback(
        db,
        alert_id=alert_id,
        alert_time=alert_time_dt,
        feedback_score=body.feedback_score,
        feedback_notes=body.feedback_notes,
    )
    return {
        "status": "success",
        "updated_active": updated_active,
        "updated_archive": updated_archive,
    }


@router.get("/performance")
async def get_alerts_performance(
    days: int = 30,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Statistical performance scorecard for screener alerts.
    Delegates the CTE+FILTER aggregation to services.alerts_analytics.
    """
    return await compute_performance_scorecard(db, days)
