"""
services/alarm_metrics_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Service for calculating and retrieving alarm metrics and KPIs.
"""
from __future__ import annotations

import logging
from datetime import date as _date, datetime
from typing import Optional

import asyncpg

from validation import EASTERN_TZ

log = logging.getLogger(__name__)

EASTERN = EASTERN_TZ


async def compute_hourly_metrics(
    db: asyncpg.Connection, target_date: _date, hour: int
) -> dict:
    """
    Compute alarm metrics for a specific hour of a specific date.
    Returns a dict ready to be inserted into alerts.alarm_metrics.
    """
    start_dt = EASTERN.localize(datetime(target_date.year, target_date.month, target_date.day, hour, 0, 0))
    end_dt = EASTERN.localize(datetime(target_date.year, target_date.month, target_date.day, hour, 59, 59, 999999))

    stats_row = await db.fetchrow(
        """
        SELECT 
            COUNT(*) as total_alarms,
            COUNT(CASE WHEN priority_tier = 'Tier 1' THEN 1 END) as tier1,
            COUNT(CASE WHEN priority_tier = 'Tier 2' THEN 1 END) as tier2,
            COUNT(CASE WHEN priority_tier = 'Tier 3' THEN 1 END) as tier3,
            COUNT(DISTINCT symbol) as unique_tickers,
            COUNT(CASE WHEN feedback_score = 'noise' THEN 1 END) as noise,
            COUNT(CASE WHEN feedback_score = 'helpful' THEN 1 END) as helpful
        FROM public.screener_alerts
        WHERE alert_time >= $1 AND alert_time <= $2
        """,
        start_dt, end_dt
    )

    chattering_row = await db.fetchval(
        """
        SELECT COALESCE(SUM(chatter_count), 0) FROM (
            SELECT COUNT(*) as chatter_count
            FROM public.screener_alerts
            WHERE alert_time >= $1 AND alert_time <= $2
            GROUP BY symbol, alert_type, date_trunc('minute', alert_time)
            HAVING COUNT(*) > 3
        ) sub
        """,
        start_dt, end_dt
    )

    peak_10min = await db.fetchval(
        """
        SELECT COALESCE(MAX(cnt), 0) FROM (
            SELECT COUNT(*) as cnt
            FROM public.screener_alerts
            WHERE alert_time >= $1 AND alert_time <= $2
            GROUP BY time_bucket('10 minutes', alert_time)
        ) sub
        """,
        start_dt, end_dt
    )

    total = stats_row['total_alarms'] or 0
    noise = stats_row['noise'] or 0
    helpful = stats_row['helpful'] or 0
    snr_pct = None
    if (helpful + noise) > 0:
        snr_pct = float(round((helpful / (helpful + noise)) * 100, 1))

    return {
        "metric_date": target_date,
        "metric_hour": hour,
        "total_alarms": total,
        "tier1_count": stats_row['tier1'] or 0,
        "tier2_count": stats_row['tier2'] or 0,
        "tier3_count": stats_row['tier3'] or 0,
        "unique_tickers": stats_row['unique_tickers'] or 0,
        "chattering_count": int(chattering_row),
        "peak_10min_rate": int(peak_10min),
        "noise_count": noise,
        "helpful_count": helpful,
        "snr_pct": snr_pct
    }


async def compute_daily_rollup(
    db: asyncpg.Connection, target_date: _date
) -> dict:
    """
    Compute daily alarm metrics rollup.
    Calculates directly from screener_alerts to ensure correctness.
    """
    start_dt = EASTERN.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0))
    end_dt = EASTERN.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999))

    stats_row = await db.fetchrow(
        """
        SELECT 
            COUNT(*) as total_alarms,
            COUNT(CASE WHEN priority_tier = 'Tier 1' THEN 1 END) as tier1,
            COUNT(CASE WHEN priority_tier = 'Tier 2' THEN 1 END) as tier2,
            COUNT(CASE WHEN priority_tier = 'Tier 3' THEN 1 END) as tier3,
            COUNT(DISTINCT symbol) as unique_tickers,
            COUNT(CASE WHEN feedback_score = 'noise' THEN 1 END) as noise,
            COUNT(CASE WHEN feedback_score = 'helpful' THEN 1 END) as helpful
        FROM public.screener_alerts
        WHERE alert_time >= $1 AND alert_time <= $2
        """,
        start_dt, end_dt
    )

    chattering_row = await db.fetchval(
        """
        SELECT COALESCE(SUM(chatter_count), 0) FROM (
            SELECT COUNT(*) as chatter_count
            FROM public.screener_alerts
            WHERE alert_time >= $1 AND alert_time <= $2
            GROUP BY symbol, alert_type, date_trunc('minute', alert_time)
            HAVING COUNT(*) > 3
        ) sub
        """,
        start_dt, end_dt
    )

    peak_10min = await db.fetchval(
        """
        SELECT COALESCE(MAX(cnt), 0) FROM (
            SELECT COUNT(*) as cnt
            FROM public.screener_alerts
            WHERE alert_time >= $1 AND alert_time <= $2
            GROUP BY time_bucket('10 minutes', alert_time)
        ) sub
        """,
        start_dt, end_dt
    )

    total = stats_row['total_alarms'] or 0
    noise = stats_row['noise'] or 0
    helpful = stats_row['helpful'] or 0
    snr_pct = None
    if (helpful + noise) > 0:
        snr_pct = float(round((helpful / (helpful + noise)) * 100, 1))

    return {
        "metric_date": target_date,
        "metric_hour": None,
        "total_alarms": total,
        "tier1_count": stats_row['tier1'] or 0,
        "tier2_count": stats_row['tier2'] or 0,
        "tier3_count": stats_row['tier3'] or 0,
        "unique_tickers": stats_row['unique_tickers'] or 0,
        "chattering_count": int(chattering_row),
        "peak_10min_rate": int(peak_10min),
        "noise_count": noise,
        "helpful_count": helpful,
        "snr_pct": snr_pct
    }


async def save_alarm_metrics(db: asyncpg.Connection, metrics: dict) -> None:
    """
    Save or update alarm metrics row in the database.
    """
    await db.execute(
        """
        INSERT INTO alerts.alarm_metrics (
            metric_date, metric_hour, total_alarms, tier1_count, tier2_count, tier3_count,
            unique_tickers, chattering_count, peak_10min_rate, noise_count, helpful_count, snr_pct
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ON CONFLICT (metric_date, metric_hour) DO UPDATE SET
            total_alarms = EXCLUDED.total_alarms,
            tier1_count = EXCLUDED.tier1_count,
            tier2_count = EXCLUDED.tier2_count,
            tier3_count = EXCLUDED.tier3_count,
            unique_tickers = EXCLUDED.unique_tickers,
            chattering_count = EXCLUDED.chattering_count,
            peak_10min_rate = EXCLUDED.peak_10min_rate,
            noise_count = EXCLUDED.noise_count,
            helpful_count = EXCLUDED.helpful_count,
            snr_pct = EXCLUDED.snr_pct
        """,
        metrics["metric_date"],
        metrics["metric_hour"],
        metrics["total_alarms"],
        metrics["tier1_count"],
        metrics["tier2_count"],
        metrics["tier3_count"],
        metrics["unique_tickers"],
        metrics["chattering_count"],
        metrics["peak_10min_rate"],
        metrics["noise_count"],
        metrics["helpful_count"],
        metrics["snr_pct"]
    )


async def get_alarm_rate_trend(
    db: asyncpg.Connection, days: int = 30
) -> list[dict]:
    """
    Retrieve alarm metrics trend for the last N days.
    Dynamically computes and inserts today's metrics if not already present.
    """
    rows = await db.fetch(
        """
        SELECT 
            metric_date::text as date,
            total_alarms,
            tier1_count,
            tier2_count,
            tier3_count,
            unique_tickers,
            chattering_count,
            peak_10min_rate,
            noise_count,
            helpful_count,
            snr_pct
        FROM alerts.alarm_metrics
        WHERE metric_hour IS NULL
        ORDER BY metric_date DESC
        LIMIT $1
        """,
        days
    )
    results = list(reversed([dict(r) for r in rows]))
    
    # Check if today (Eastern) is in the results
    today_str = datetime.now(EASTERN).date().isoformat()
    has_today = any(r["date"] == today_str for r in results)
    
    if not has_today:
        try:
            today_date = datetime.now(EASTERN).date()
            # Calculate today's rollup dynamically
            today_rollup = await compute_daily_rollup(db, today_date)
            # Save it so next call is fast (upsert)
            await save_alarm_metrics(db, today_rollup)
            
            # Format and append
            today_formatted = {
                "date": today_str,
                "total_alarms": today_rollup["total_alarms"],
                "tier1_count": today_rollup["tier1_count"],
                "tier2_count": today_rollup["tier2_count"],
                "tier3_count": today_rollup["tier3_count"],
                "unique_tickers": today_rollup["unique_tickers"],
                "chattering_count": today_rollup["chattering_count"],
                "peak_10min_rate": today_rollup["peak_10min_rate"],
                "noise_count": today_rollup["noise_count"],
                "helpful_count": today_rollup["helpful_count"],
                "snr_pct": today_rollup["snr_pct"]
            }
            results.append(today_formatted)
            # If results length exceeds days, trim the oldest
            if len(results) > days:
                results.pop(0)
        except Exception as e:
            log.error("Failed to dynamically compute today's alarm metrics: %s", e)
            
    return results


async def get_bad_actors(
    db: asyncpg.Connection, days: int = 30, top_n: int = 10
) -> list[dict]:
    """
    Retrieve top bad actors (ticker + alert type combos) for the last N days.
    """
    rows = await db.fetch(
        """
        SELECT 
            symbol,
            alert_type,
            COUNT(*) as fire_count,
            COUNT(CASE WHEN feedback_score = 'noise' THEN 1 END) as noise_count,
            COUNT(CASE WHEN feedback_score = 'helpful' THEN 1 END) as helpful_count,
            COALESCE(ROUND(COUNT(CASE WHEN feedback_score = 'noise' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN feedback_score IN ('noise', 'helpful') THEN 1 END), 0), 1), 0.0) as noise_pct
        FROM public.screener_alerts
        WHERE alert_time >= NOW() - ($1 * INTERVAL '1 day')
        GROUP BY symbol, alert_type
        ORDER BY fire_count DESC
        LIMIT $2
        """,
        days, top_n
    )
    return [dict(r) for r in rows]


async def get_chattering_alerts(
    db: asyncpg.Connection, target_date: _date
) -> list[dict]:
    """
    Retrieve list of chattering alerts for a specific date.
    """
    start_dt = EASTERN.localize(datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0))
    end_dt = EASTERN.localize(datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999))

    rows = await db.fetch(
        """
        SELECT symbol, alert_type, COUNT(*) as fire_count,
               MIN(alert_time) as first_time, MAX(alert_time) as last_time
        FROM public.screener_alerts
        WHERE alert_time >= $1 AND alert_time <= $2
        GROUP BY symbol, alert_type, date_trunc('minute', alert_time)
        HAVING COUNT(*) > 3
        ORDER BY fire_count DESC
        """,
        start_dt, end_dt
    )
    return [dict(r) for r in rows]
