#!/usr/bin/env python3
"""
Pull historical data from historicalpercentgainers.com
Usage:
  python pull_historical.py
"""
import sys
import os
import requests
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import get_connection

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

DATA_URL = "https://www.historicalpercentgainers.com/static/top_gainers.json"

def main():
    log.info(f"Fetching data from {DATA_URL}...")
    try:
        r = requests.get(DATA_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.error(f"Failed to fetch data: {e}")
        sys.exit(1)

    log.info(f"Found {len(data)} historical records. Inserting into database...")

    inserted = 0
    skipped = 0
    errors = 0

    with get_connection() as conn:
        for row in data:
            try:
                date = row.get('Date', '').strip()
                ticker = row.get('symbol', '').strip().upper()
                percent_gain = row.get('percent_gain')

                if not date or not ticker:
                    skipped += 1
                    continue

                # Map percent_gain to gap_pct for historical tracking
                try:
                    gap_pct = float(percent_gain) if percent_gain is not None else None
                except ValueError:
                    gap_pct = None

                # We don't have these fields from this source, but we can fill them later or leave NULL
                float_shares = None
                rvol = None
                sector = None
                market_cap = None
                news_headline = None
                news_fresh = False
                close_price = None
                open_price = None

                conn.execute(
                    """INSERT INTO daily_gainers
                       (date, ticker, gap_pct, float_shares, rvol_15m, sector,
                        market_cap, news_headline, news_fresh, close_price, open_price)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        date, ticker, gap_pct, float_shares, rvol, sector,
                        market_cap, news_headline, news_fresh, close_price, open_price
                    )
                )
                inserted += 1

            except Exception as e:
                if 'unique' in str(e).lower():
                    skipped += 1
                else:
                    log.error(f"Error inserting {ticker} on {date}: {e}")
                    errors += 1

    log.info(f"Import complete: {inserted} inserted, {skipped} skipped (duplicates/missing data), {errors} errors.")

if __name__ == '__main__':
    main()
