#!/usr/bin/env python3
import sys
import os
import asyncio
import asyncpg
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import settings
from services.alarm_metrics_service import compute_hourly_metrics, compute_daily_rollup, save_alarm_metrics

async def backfill():
    print(f"Connecting to database using DSN: {settings.asyncpg_dsn}")
    conn = await asyncpg.connect(dsn=settings.asyncpg_dsn)
    try:
        # Find all distinct dates that have alerts
        print("Fetching distinct dates from screener_alerts...")
        rows = await conn.fetch(
            "SELECT DISTINCT alert_time::date as date_val FROM public.screener_alerts ORDER BY date_val DESC LIMIT 30"
        )
        dates = [row['date_val'] for row in rows]
        print(f"Found {len(dates)} dates to backfill: {dates}")

        for target_date in dates:
            print(f"\n--- Backfilling date: {target_date} ---")
            for hour in range(24):
                print(f"Computing metrics for hour {hour:02d}...", end="\r")
                metrics = await compute_hourly_metrics(conn, target_date, hour)
                await save_alarm_metrics(conn, metrics)
            print(f"Computing metrics for hour 23... Done.")
            
            print(f"Computing daily rollup metrics...")
            daily_metrics = await compute_daily_rollup(conn, target_date)
            await save_alarm_metrics(conn, daily_metrics)
            print(f"Successfully backfilled metrics for {target_date}")

        print("\nAll backfills completed successfully!")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(backfill())
