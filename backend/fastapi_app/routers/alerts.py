import os
import asyncio
import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import asyncpg
import redis.asyncio as aioredis

from fastapi_app.db import get_db, rows_to_list

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
