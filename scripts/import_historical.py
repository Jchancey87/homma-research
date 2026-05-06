#!/usr/bin/env python3
"""
Historical data import script for Phase 5.
Maps a custom CSV format into the `daily_gainers` table.

Usage:
  python import_historical.py /path/to/historical.csv
"""
import sys
import os
import csv
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import get_connection

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Adjust these constants to match your actual CSV column names
# ---------------------------------------------------------------------------
COL_DATE          = 'Date'
COL_TICKER        = 'Ticker'
COL_GAP_PCT       = 'Gap %'
COL_FLOAT         = 'Float'       # Assuming raw shares, e.g. 15000000
COL_RVOL          = 'RVOL'
COL_SECTOR        = 'Sector'
COL_MARKET_CAP    = 'Market Cap'
COL_NEWS_HEADLINE = 'News'
COL_CLOSE         = 'Close'
COL_OPEN          = 'Open'

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        log.error(f"File not found: {csv_path}")
        sys.exit(1)

    inserted = 0
    skipped  = 0
    errors   = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        with get_connection() as conn:
            for row in reader:
                try:
                    date   = row.get(COL_DATE, '').strip()
                    ticker = row.get(COL_TICKER, '').strip().upper()

                    if not date or not ticker:
                        log.warning(f"Skipping row missing date or ticker: {row}")
                        skipped += 1
                        continue

                    def parse_float(val):
                        if not val: return None
                        try:
                            # remove commas and % signs
                            cleaned = str(val).replace(',', '').replace('%', '').strip()
                            return float(cleaned)
                        except ValueError:
                            return None

                    gap_pct       = parse_float(row.get(COL_GAP_PCT))
                    float_shares  = parse_float(row.get(COL_FLOAT))
                    rvol          = parse_float(row.get(COL_RVOL))
                    sector        = row.get(COL_SECTOR, '').strip() or None
                    market_cap    = parse_float(row.get(COL_MARKET_CAP))
                    news_headline = row.get(COL_NEWS_HEADLINE, '').strip() or None
                    close_price   = parse_float(row.get(COL_CLOSE))
                    open_price    = parse_float(row.get(COL_OPEN))

                    # Assume news is stale for historical data unless otherwise classified
                    news_fresh = False

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
                        log.error(f"Error inserting {row.get(COL_TICKER)} on {row.get(COL_DATE)}: {e}")
                        errors += 1

    log.info(f"Import complete: {inserted} inserted, {skipped} skipped (duplicates/missing data), {errors} errors.")

if __name__ == '__main__':
    main()
