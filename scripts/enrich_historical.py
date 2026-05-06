#!/usr/bin/env python3
"""
Enrich historical daily_gainers data with proper metrics from yfinance.

This script fixes two problems with the raw historicalpercentgainers.com import:
  1. gap_pct is wildly wrong (full-day move, not gap; includes split artifacts)
  2. float_shares, rvol_15m, sector, market_cap are all NULL

What this script does:
  1. Removes suspect records (gap_pct > 2000%) — these are almost always
     reverse-split artifacts or data errors, not real gaps.
  2. Groups remaining records by ticker to minimize yfinance API calls.
  3. For each ticker, downloads the full OHLCV history in one request.
  4. Recalculates gap_pct = (open - prev_close) / prev_close * 100 for each date.
  5. Calculates RVOL = day_volume / 20-day_avg_volume_prior_to_that_day.
  6. Fetches static info (float, sector, market_cap) once per ticker.
  7. Deletes rows that calculate to gap_pct < 10% (not a real gapper day)
     or to gap_pct > 500% (still likely a bad data point).
  8. Updates all remaining rows with the enriched data.

Usage:
  python enrich_historical.py [--dry-run] [--ticker AAPL] [--limit 100]

Options:
  --dry-run     Print what would happen without writing to DB
  --ticker SYM  Only process a specific ticker (useful for testing)
  --limit N     Only process first N unique tickers (useful for testing)
  --workers N   Thread workers for parallel info fetching (default: 4)
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import yfinance as yf
import pandas as pd
from database import get_connection, init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)


# ─── Thresholds ────────────────────────────────────────────────────────────────
MAX_SUSPECT_GAP  = 2000.0   # Remove records above this from the HPG import
MAX_REAL_GAP     = 500.0    # After yfinance recalc, discard if still > 500%
MIN_REAL_GAP     = 10.0     # Must be at least a 10% gap to count
RVOL_WINDOW_DAYS = 20       # Days of prior volume to average for RVOL
SLEEP_BETWEEN    = 0.3      # Seconds to sleep between yfinance requests


def main():
    parser = argparse.ArgumentParser(description='Enrich historical gainer data with yfinance')
    parser.add_argument('--dry-run',  action='store_true', help='Print without writing to DB')
    parser.add_argument('--ticker',   help='Only process this ticker')
    parser.add_argument('--limit',    type=int, default=None, help='Limit number of tickers')
    parser.add_argument('--workers',  type=int, default=4,    help='Parallel workers for info fetch')
    args = parser.parse_args()

    init_db()

    # Step 1: Delete suspect records
    if not args.dry_run:
        with get_connection() as conn:
            deleted = conn.execute(
                "DELETE FROM daily_gainers WHERE gap_pct > %s", (MAX_SUSPECT_GAP,)
            ).rowcount
        log.info(f"Removed {deleted} suspect records (gap_pct > {MAX_SUSPECT_GAP}%)")
    else:
        with get_connection() as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) AS count FROM daily_gainers WHERE gap_pct > %s", (MAX_SUSPECT_GAP,)
            ).fetchone()['count']
        log.info(f"[DRY RUN] Would remove {cnt} suspect records")

    # Step 2: Load all records that still need enrichment
    if args.ticker:
        filter_clause = "WHERE ticker = %s ORDER BY date"
        filter_params = (args.ticker.upper(),)
    else:
        filter_clause = "ORDER BY ticker, date"
        filter_params = ()

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, ticker, date, gap_pct FROM daily_gainers {filter_clause}",
            filter_params
        ).fetchall()

    # Group by ticker
    from collections import defaultdict
    ticker_dates: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        ticker_dates[row['ticker']].append({'id': row['id'], 'date': row['date']})

    tickers = list(ticker_dates.keys())
    if args.limit:
        tickers = tickers[:args.limit]

    log.info(f"Processing {len(tickers)} unique tickers across {len(rows)} records")

    # Step 3: Process each ticker
    stats = {'updated': 0, 'deleted_bad_gap': 0, 'no_data': 0, 'errors': 0}

    for i, ticker in enumerate(tickers):
        records = ticker_dates[ticker]
        try:
            result = process_ticker(ticker, records, args.dry_run)
            stats['updated']          += result['updated']
            stats['deleted_bad_gap']  += result['deleted_bad_gap']
            stats['no_data']          += result['no_data']
        except Exception as e:
            log.error(f"[{ticker}] Fatal error: {e}")
            stats['errors'] += 1

        # Progress
        if (i + 1) % 50 == 0 or i == len(tickers) - 1:
            log.info(f"Progress: {i+1}/{len(tickers)} tickers | "
                     f"updated={stats['updated']} removed={stats['deleted_bad_gap']} "
                     f"no_data={stats['no_data']} errors={stats['errors']}")

        time.sleep(SLEEP_BETWEEN)

    log.info("=" * 60)
    log.info(f"Enrichment complete:")
    log.info(f"  Records updated:      {stats['updated']}")
    log.info(f"  Removed (bad gap):    {stats['deleted_bad_gap']}")
    log.info(f"  Removed (no yf data): {stats['no_data']}")
    log.info(f"  Ticker errors:        {stats['errors']}")


def process_ticker(ticker: str, records: list[dict], dry_run: bool) -> dict:
    """
    Download OHLCV + info for one ticker, recalculate gap/RVOL, update DB.
    Returns counts of outcomes.
    """
    result = {'updated': 0, 'deleted_bad_gap': 0, 'no_data': 0}

    # Find the earliest date we need
    dates = sorted(r['date'] for r in records)
    earliest = datetime.strptime(dates[0], '%Y-%m-%d') - timedelta(days=60)
    latest   = datetime.strptime(dates[-1], '%Y-%m-%d') + timedelta(days=1)

    # Download OHLCV history
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(
            start=earliest.strftime('%Y-%m-%d'),
            end=latest.strftime('%Y-%m-%d'),
            interval='1d',
            auto_adjust=True,
        )
    except Exception as e:
        log.warning(f"[{ticker}] yfinance download failed: {e}")
        if not dry_run:
            _delete_records(records)
        result['no_data'] += len(records)
        return result

    if hist.empty:
        log.warning(f"[{ticker}] No historical data from yfinance")
        if not dry_run:
            _delete_records(records)
        result['no_data'] += len(records)
        return result

    # Normalise index to tz-naive date-only for easy lookup
    hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()

    # Get static info (float, sector, market cap) — one call per ticker
    info = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    float_shares = info.get('floatShares') or info.get('sharesOutstanding')
    sector       = info.get('sector') or info.get('industry')
    market_cap   = info.get('marketCap')

    for rec in records:
        rec_date = datetime.strptime(rec['date'], '%Y-%m-%d')
        rec_id   = rec['id']

        # Find the trading day row for this date
        date_key = pd.Timestamp(rec_date).normalize()
        if date_key not in hist.index:
            # Trading day not in history (holiday, halt, etc.)
            if not dry_run:
                _delete_records([rec])
            result['no_data'] += 1
            continue

        row_idx  = hist.index.get_loc(date_key)
        today_row = hist.iloc[row_idx]

        # Need at least one prior day to compute gap
        if row_idx == 0:
            if not dry_run:
                _delete_records([rec])
            result['no_data'] += 1
            continue

        prev_row  = hist.iloc[row_idx - 1]
        prev_close = float(prev_row['Close'])
        open_price = float(today_row['Open'])
        close_price = float(today_row['Close'])

        if prev_close == 0:
            if not dry_run:
                _delete_records([rec])
            result['no_data'] += 1
            continue

        # True gap calculation
        gap_pct = ((open_price - prev_close) / prev_close) * 100

        # Filter out non-gapper days and still-crazy values
        if gap_pct < MIN_REAL_GAP or gap_pct > MAX_REAL_GAP:
            if not dry_run:
                _delete_records([rec])
            result['deleted_bad_gap'] += 1
            continue

        # RVOL: day volume vs prior 20-day average
        start_window = max(0, row_idx - RVOL_WINDOW_DAYS)
        prior_slice  = hist.iloc[start_window:row_idx]
        day_volume   = float(today_row['Volume'])
        avg_volume   = float(prior_slice['Volume'].mean()) if len(prior_slice) > 0 else 0
        rvol         = round(day_volume / avg_volume, 2) if avg_volume > 0 else None

        if dry_run:
            log.info(f"[DRY RUN] {ticker} {rec['date']}: "
                     f"gap={gap_pct:.1f}% rvol={rvol} float={float_shares} sector={sector}")
            result['updated'] += 1
            continue

        # Update the record
        with get_connection() as conn:
            conn.execute(
                """UPDATE daily_gainers
                   SET gap_pct      = %s,
                       float_shares = %s,
                       rvol_15m     = %s,
                       sector       = %s,
                       market_cap   = %s,
                       open_price   = %s,
                       close_price  = %s
                   WHERE id = %s""",
                (
                    round(gap_pct, 2),
                    float_shares,
                    rvol,
                    sector,
                    market_cap,
                    round(open_price, 4),
                    round(close_price, 4),
                    rec_id,
                )
            )
        result['updated'] += 1

    return result


def _delete_records(records: list[dict]):
    ids = [r['id'] for r in records]
    if not ids:
        return
    # psycopg2 uses %s; build a placeholder tuple
    placeholders = ','.join(['%s'] * len(ids))
    with get_connection() as conn:
        conn.execute(
            f"DELETE FROM daily_gainers WHERE id IN ({placeholders})",
            ids
        )


if __name__ == '__main__':
    main()
