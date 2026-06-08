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


from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException
from collections import defaultdict
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
    joined with stock fundamentals.
    """
    date_str = date
    if not date_str:
        row = await db.fetchrow("""
            SELECT (alert_time AT TIME ZONE 'America/New_York')::date AS last_date
            FROM public.screener_alerts
            ORDER BY alert_time DESC
            LIMIT 1
        """)
        if row and row['last_date']:
            date_str = row['last_date'].isoformat()
        else:
            from datetime import datetime
            import pytz
            date_str = datetime.now(pytz.timezone('America/New_York')).date().isoformat()

    try:
        query_date = date_cls.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Must be YYYY-MM-DD.")

    # Query alerts and join fundamentals
    rows = await db.fetch("""
        SELECT a.id, a.symbol, a.alert_time, a.trigger_price, a.trigger_volume,
               a.rel_vol, a.gap_pct, a.float_shares, a.alert_type, a.sent,
               a.feedback_score, a.feedback_notes,
               f.company_name, f.float_category, f.market_cap
        FROM public.screener_alerts a
        LEFT JOIN public.stock_fundamentals f ON a.symbol = f.symbol
        WHERE (a.alert_time AT TIME ZONE 'America/New_York')::date = $1
        ORDER BY a.symbol, a.alert_time ASC
    """, query_date)

    # ── Compute forward returns & excursions for each alert ─────────────────────
    # Uses 1-minute candle data from price_history_1min (TimescaleDB hypertable)
    async def get_forward_returns(alert_id: int, symbol: str, alert_time, trigger_price: float) -> dict:
        """Calculate 1m/3m/5m/15m forward returns, MFE, and MAE from 1-min candle data."""
        try:
            candles = await db.fetch("""
                SELECT timestamp, open, high, low, close
                FROM price_history_1min
                WHERE symbol = $1
                  AND timestamp >= $2
                  AND timestamp <= $2 + INTERVAL '16 minutes'
                ORDER BY timestamp ASC
            """, symbol, alert_time)

            if not candles or trigger_price <= 0:
                return {}

            results = {}
            highs, lows = [], []
            for i, c in enumerate(candles):
                highs.append(float(c['high']))
                lows.append(float(c['low']))
                close = float(c['close'])
                ret = (close - trigger_price) / trigger_price * 100.0
                minute = i + 1
                if minute == 1:
                    results['fwd_1m'] = round(ret, 2)
                elif minute == 3:
                    results['fwd_3m'] = round(ret, 2)
                elif minute == 5:
                    results['fwd_5m'] = round(ret, 2)
                elif minute == 15:
                    results['fwd_15m'] = round(ret, 2)

            if highs:
                results['mfe'] = round((max(highs) - trigger_price) / trigger_price * 100.0, 2)
            if lows:
                results['mae'] = round((min(lows) - trigger_price) / trigger_price * 100.0, 2)

            return results
        except Exception as exc:
            logger.warning("Forward return calc failed for alert %s: %s", alert_id, exc)
            return {}

    import asyncio as _asyncio
    fwd_tasks = [
        get_forward_returns(r["id"], r["symbol"], r["alert_time"], float(r["trigger_price"] or 0))
        for r in rows
    ]
    fwd_results = await _asyncio.gather(*fwd_tasks)
    fwd_by_id = {rows[i]["id"]: fwd_results[i] for i in range(len(rows))}

    # Group by symbol
    ticker_groups = defaultdict(lambda: {
        "symbol": "",
        "company_name": None,
        "float_category": None,
        "float_shares": None,
        "market_cap": None,
        "gap_pct": None,
        "rvol": None,
        "alerts": []
    })

    for r in rows:
        sym = r['symbol']
        group = ticker_groups[sym]
        if not group["symbol"]:
            group["symbol"] = sym
            group["company_name"] = r.get("company_name")
            group["float_category"] = r.get("float_category")
            group["float_shares"] = r.get("float_shares")
            group["market_cap"] = r.get("market_cap")
            group["gap_pct"] = r.get("gap_pct")
            group["rvol"] = r.get("rel_vol")

        fwd = fwd_by_id.get(r["id"], {})
        group["alerts"].append({
            "id": r["id"],
            "alert_time": r["alert_time"].isoformat(),
            "trigger_price": r["trigger_price"],
            "trigger_volume": r["trigger_volume"],
            "rel_vol": r["rel_vol"],
            "alert_type": r["alert_type"],
            "feedback_score": r.get("feedback_score"),
            "feedback_notes": r.get("feedback_notes"),
            "fwd_1m": fwd.get("fwd_1m"),
            "fwd_3m": fwd.get("fwd_3m"),
            "fwd_5m": fwd.get("fwd_5m"),
            "fwd_15m": fwd.get("fwd_15m"),
            "mfe": fwd.get("mfe"),
            "mae": fwd.get("mae"),
        })

    return {
        "date": date_str,
        "tickers": list(ticker_groups.values())
    }

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
    Returns win rates, expectancy, and average forward returns grouped by:
      - alert_type
      - price_bucket ($1-2, $2-5, $5-15, $15+)
      - float_category
    Only alerts where 5-minute forward return data exists in price_history_1min
    are counted (others are excluded from stats to avoid survivor bias).
    """
    rows = await db.fetch("""
        WITH alert_fwd AS (
            SELECT
                a.id,
                a.alert_type,
                a.trigger_price,
                f.float_category,
                CASE
                    WHEN a.trigger_price < 2   THEN '$1-2'
                    WHEN a.trigger_price < 5   THEN '$2-5'
                    WHEN a.trigger_price < 15  THEN '$5-15'
                    ELSE '$15+'
                END AS price_bucket,
                -- 5-minute forward return from 1-min candle data
                (
                    SELECT (ph.close - a.trigger_price) / a.trigger_price * 100.0
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time + INTERVAL '4 minutes 30 seconds'
                      AND ph.timestamp <= a.alert_time + INTERVAL '5 minutes 30 seconds'
                    ORDER BY ph.timestamp ASC
                    LIMIT 1
                ) AS fwd_5m,
                -- 15-minute forward return
                (
                    SELECT (ph.close - a.trigger_price) / a.trigger_price * 100.0
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time + INTERVAL '14 minutes 30 seconds'
                      AND ph.timestamp <= a.alert_time + INTERVAL '15 minutes 30 seconds'
                    ORDER BY ph.timestamp ASC
                    LIMIT 1
                ) AS fwd_15m,
                -- MFE (max favorable excursion, 15m window)
                (
                    SELECT MAX(ph.high)
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time
                      AND ph.timestamp <= a.alert_time + INTERVAL '15 minutes'
                ) AS mfe_high,
                -- MAE (max adverse excursion, 15m window)
                (
                    SELECT MIN(ph.low)
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time
                      AND ph.timestamp <= a.alert_time + INTERVAL '15 minutes'
                ) AS mae_low
            FROM public.screener_alerts a
            LEFT JOIN public.stock_fundamentals f ON a.symbol = f.symbol
            WHERE a.alert_time >= NOW() - ($1 || ' days')::INTERVAL
              AND a.trigger_price > 0
        )
        SELECT
            alert_type,
            price_bucket,
            float_category,
            COUNT(*) FILTER (WHERE fwd_5m IS NOT NULL) AS sample_count,
            ROUND(AVG(fwd_5m) FILTER (WHERE fwd_5m IS NOT NULL)::numeric, 2) AS avg_fwd_5m,
            ROUND(AVG(fwd_15m) FILTER (WHERE fwd_15m IS NOT NULL)::numeric, 2) AS avg_fwd_15m,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE fwd_5m IS NOT NULL AND fwd_5m > 0)
                / NULLIF(COUNT(*) FILTER (WHERE fwd_5m IS NOT NULL), 0),
                1
            ) AS win_rate_5m_pct,
            ROUND(
                AVG(
                    CASE WHEN mfe_high IS NOT NULL AND trigger_price > 0
                         THEN (mfe_high - trigger_price) / trigger_price * 100.0
                    END
                )::numeric, 2
            ) AS avg_mfe_pct,
            ROUND(
                AVG(
                    CASE WHEN mae_low IS NOT NULL AND trigger_price > 0
                         THEN (mae_low - trigger_price) / trigger_price * 100.0
                    END
                )::numeric, 2
            ) AS avg_mae_pct
        FROM alert_fwd
        GROUP BY alert_type, price_bucket, float_category
        ORDER BY alert_type, price_bucket, float_category
    """, str(days))

    return {
        "days": days,
        "scorecard": [
            {
                "alert_type": r["alert_type"],
                "price_bucket": r["price_bucket"],
                "float_category": r["float_category"],
                "sample_count": r["sample_count"],
                "avg_fwd_5m": float(r["avg_fwd_5m"]) if r["avg_fwd_5m"] is not None else None,
                "avg_fwd_15m": float(r["avg_fwd_15m"]) if r["avg_fwd_15m"] is not None else None,
                "win_rate_5m_pct": float(r["win_rate_5m_pct"]) if r["win_rate_5m_pct"] is not None else None,
                "avg_mfe_pct": float(r["avg_mfe_pct"]) if r["avg_mfe_pct"] is not None else None,
                "avg_mae_pct": float(r["avg_mae_pct"]) if r["avg_mae_pct"] is not None else None,
            }
            for r in rows
        ]
    }
