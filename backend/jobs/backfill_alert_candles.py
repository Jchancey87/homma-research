#!/usr/bin/env python3
"""
Nightly 1-minute candle backfill for alerted stocks.
Queries all stocks that triggered alerts today and ensures
their 1-minute candles are present in the price_history_1min table.
"""
import sys
import os
import time
import argparse
import logging
from datetime import datetime, timedelta, date as date_cls
import pytz

# Add paths
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from config import Config
from database import get_connection
from services.schwab_client import get_price_history_every_minute

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

RATE_LIMIT_DELAY = 0.6  # delay between Schwab API calls

def backfill_alert_candles(target_date: date_cls):
    """
    Find symbols that triggered alerts on target_date,
    check if their 1-minute candles are present, and backfill if missing.
    """
    log.info(f"Starting alert candle backfill for {target_date}...")
    
    # 1. Get unique symbols that triggered alerts on target_date (US/Eastern timezone)
    tz_et = pytz.timezone('America/New_York')
    
    with get_connection() as conn:
        cur = conn._conn.cursor()
        # Find alerts where alert_time falls on target_date in Eastern Time
        cur.execute("""
            SELECT DISTINCT symbol 
            FROM public.screener_alerts 
            WHERE (alert_time AT TIME ZONE 'America/New_York')::date = %s
        """, (target_date,))
        rows = cur.fetchall()
        symbols = [r['symbol'] if isinstance(r, dict) else r[0] for r in rows]
        
    if not symbols:
        log.info(f"No alerted symbols found in screener_alerts for {target_date}.")
        return

    log.info(f"Found {len(symbols)} symbols with alerts on {target_date}: {symbols}")
    
    # Define start and end datetime in Eastern Time for the target_date
    start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz_et)
    end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=tz_et)
    
    for idx, sym in enumerate(symbols):
        try:
            # 2. Check if we already have candles for this symbol and date
            with get_connection() as conn:
                cur = conn._conn.cursor()
                cur.execute("""
                    SELECT COUNT(*) as count 
                    FROM public.price_history_1min 
                    WHERE symbol = %s AND (timestamp AT TIME ZONE 'America/New_York')::date = %s
                """, (sym, target_date))
                row = cur.fetchone()
                count = row['count'] if isinstance(row, dict) else row[0]
                
            # If we have less than 350 candles, let's backfill
            if count >= 350:
                log.info(f"[{sym}] Already has {count} candles in database. Skipping backfill.")
                continue
                
            log.info(f"[{sym}] Has {count} candles. Fetching 1-minute bars from Schwab...")
            
            candles = get_price_history_every_minute(sym, start_datetime=start_dt, end_datetime=end_dt)
            if not candles:
                log.warning(f"[{sym}] No candles returned from Schwab API.")
                time.sleep(RATE_LIMIT_DELAY)
                continue
                
            # Prepare rows
            records = []
            for c in candles:
                ts_ms = c.get('datetime')
                if not ts_ms:
                    continue
                ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=pytz.UTC)
                
                records.append((
                    sym,
                    ts,
                    c.get('open'),
                    c.get('high'),
                    c.get('low'),
                    c.get('close'),
                    c.get('volume')
                ))
                
            if records:
                with get_connection() as conn:
                    cur = conn._conn.cursor()
                    cur.executemany("""
                        INSERT INTO price_history_1min (symbol, timestamp, open, high, low, close, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, timestamp) DO NOTHING
                    """, records)
                log.info(f"[{sym}] Ingested {len(records)} candles.")
                
        except Exception as e:
            log.error(f"[{sym}] Failed to backfill candles: {e}")
            
        time.sleep(RATE_LIMIT_DELAY)
        
    log.info(f"Alert candle backfill completed for {target_date}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Backfill 1-minute candles for alerted stocks')
    parser.add_argument('--date', default=None, help='YYYY-MM-DD target date (defaults to today in Eastern)')
    args = parser.parse_args()
    
    # Default to today in US/Eastern
    tz_et = pytz.timezone('America/New_York')
    if args.date:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    else:
        target_date = datetime.now(tz_et).date()
        
    backfill_alert_candles(target_date)
