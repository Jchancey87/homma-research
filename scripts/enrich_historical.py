#!/usr/bin/env python3
"""
Enrich historical daily_gainers data with proper metrics from Charles Schwab API & yfinance.

This script fixes two problems with the raw historicalpercentgainers.com import:
  1. gap_pct is wildly wrong (full-day move, not gap; includes split artifacts)
  2. float_shares, rvol_15m, sector, market_cap are all NULL

What this script does:
  1. Removes suspect records (gap_pct > 2000%) — these are almost always
     reverse-split artifacts or data errors, not real gaps.
  2. Groups remaining records by ticker to minimize Schwab/yfinance API calls.
  3. For each ticker, downloads the full daily OHLCV history from Charles Schwab API.
  4. Recalculates gap_pct = (open - prev_close) / prev_close * 100 for each date.
  5. Calculates RVOL = day_volume / 20-day_avg_volume_prior_to_that_day.
  6. Fetches static info (shares outstanding, sector, market cap) from Schwab API,
     falling back to yfinance only for float_shares (which Schwab does not expose).
  7. Calculates additional metrics: high_price, low_price, prev_close, dollar_volume,
     close_location, avg_volume, and rs_vs_spy (using SPY historical bars fetched once).
  8. Deletes rows that calculate to gap_pct < 10% (not a real gapper day)
     or to gap_pct > 500% (still likely a bad data point).
  9. Updates all remaining rows with the enriched data.

Usage:
  python enrich_historical.py [--dry-run] [--ticker AAPL] [--limit 100] [--only-unenriched] [--limit-days 30]
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime, timedelta

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Load environment variables from backend/.env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

import yfinance as yf
import pandas as pd
import numpy as np
from database import get_connection, init_db
from services.schwab_client import get_daily_bars, get_ticker_details

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)


# ─── Thresholds ────────────────────────────────────────────────────────────────
MAX_SUSPECT_GAP  = 2000.0   # Remove records above this from the HPG import
MAX_REAL_GAP     = 500.0    # After recalc, discard if still > 500%
MIN_REAL_GAP     = 10.0     # Must be at least a 10% gap to count
RVOL_WINDOW_DAYS = 20       # Days of prior volume to average for RVOL
SLEEP_BETWEEN    = 0.3      # Seconds to sleep between tickers


def main():
    parser = argparse.ArgumentParser(description='Enrich historical gainer data with Schwab & yfinance')
    parser.add_argument('--dry-run',  action='store_true', help='Print without writing to DB')
    parser.add_argument('--ticker',   help='Only process this ticker')
    parser.add_argument('--limit',    type=int, default=None, help='Limit number of tickers')
    parser.add_argument('--workers',  type=int, default=4,    help='Parallel workers for info fetch (kept for compatibility)')
    parser.add_argument('--only-unenriched', action='store_true', help='Only process records with NULL rvol_15m')
    parser.add_argument('--limit-days', type=int, default=None, help='Only process records from the last N days')
    args = parser.parse_args()

    init_db()

    # Step 1: Delete suspect records (only if not running on filtered/unenriched subset to avoid deleting recalculated rows)
    if not args.only_unenriched and not args.ticker and not args.limit_days:
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

    # Step 2: Load all records that need enrichment
    conditions = []
    params = []

    if args.only_unenriched:
        conditions.append("rvol_15m IS NULL")

    if args.ticker:
        conditions.append("ticker = %s")
        params.append(args.ticker.upper())

    if args.limit_days:
        cutoff_date = (datetime.now() - timedelta(days=args.limit_days)).strftime('%Y-%m-%d')
        conditions.append("date >= %s")
        params.append(cutoff_date)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"SELECT id, ticker, date, gap_pct FROM daily_gainers {where_clause} ORDER BY ticker, date"

    with get_connection() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    # Group by ticker
    from collections import defaultdict
    ticker_dates: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        ticker_dates[row['ticker']].append({'id': row['id'], 'date': row['date']})

    tickers = list(ticker_dates.keys())
    if args.limit:
        tickers = tickers[:args.limit]

    log.info(f"Processing {len(tickers)} unique tickers across {len(rows)} records")
    if not tickers:
        log.info("No records to process.")
        return

    # Fetch SPY daily bars once to compute relative strength (rs_vs_spy)
    log.info("Fetching SPY daily price history from Schwab to compute relative strength (rs_vs_spy)...")
    spy_df = pd.DataFrame()
    try:
        spy_candles = get_daily_bars('SPY')
        if spy_candles:
            spy_df = pd.DataFrame(spy_candles)
            spy_df = spy_df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
            spy_df['date'] = pd.to_datetime(spy_df['t'], unit='ms').dt.strftime('%Y-%m-%d')
            spy_df = spy_df.set_index('date')
            log.info(f"Loaded {len(spy_df)} SPY trading days.")
        else:
            log.warning("Could not fetch SPY daily bars from Schwab. rs_vs_spy calculations will be skipped.")
    except Exception as e:
        log.warning(f"Error fetching SPY bars: {e}. rs_vs_spy calculations will be skipped.")

    # Step 3: Process each ticker
    stats = {'updated': 0, 'deleted_bad_gap': 0, 'no_data': 0, 'errors': 0}

    for i, ticker in enumerate(tickers):
        records = ticker_dates[ticker]
        try:
            result = process_ticker(ticker, records, spy_df, args.dry_run)
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
    log.info(f"  Removed (no data):     {stats['no_data']}")
    log.info(f"  Ticker errors:        {stats['errors']}")


def process_ticker(ticker: str, records: list[dict], spy_df: pd.DataFrame, dry_run: bool) -> dict:
    """
    Download OHLCV + info for one ticker, recalculate gap/RVOL, update DB.
    Returns counts of outcomes.
    """
    result = {'updated': 0, 'deleted_bad_gap': 0, 'no_data': 0}

    # Fetch daily bars from Schwab
    try:
        candles = get_daily_bars(ticker)
    except Exception as e:
        log.warning(f"[{ticker}] Schwab daily bars fetch failed: {e}")
        if not dry_run:
            _delete_records(records)
        result['no_data'] += len(records)
        return result

    # Filter out empty or incomplete bars
    if candles:
        candles = [c for c in candles if c.get('t') is not None and c.get('v') is not None]

    if not candles:
        log.warning(f"[{ticker}] No historical data from Schwab")
        if not dry_run:
            _delete_records(records)
        result['no_data'] += len(records)
        return result

    df = pd.DataFrame(candles)
    df = df.rename(columns={'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume'})
    df['date'] = pd.to_datetime(df['t'], unit='ms').dt.strftime('%Y-%m-%d')
    df = df.set_index('date')

    # Get static info from Schwab
    sector = None
    market_cap = None
    shares_outstanding = None
    try:
        details = get_ticker_details(ticker) or {}
        sector = details.get('sector')
        market_cap = details.get('market_cap')
        shares_outstanding = details.get('shares_outstanding')
    except Exception as e:
        log.debug(f"[{ticker}] Schwab ticker details failed: {e}")

    # Fallback to yfinance for float_shares (and sector/market_cap if Schwab missed)
    float_shares = None
    try:
        float_shares = _yf_float_fallback(ticker)
    except Exception:
        pass

    if not sector or not market_cap or not shares_outstanding:
        try:
            info = yf.Ticker(ticker).info or {}
            if not sector:
                sector = info.get('sector') or info.get('industry')
            if not market_cap:
                market_cap = info.get('marketCap')
            if not shares_outstanding:
                shares_outstanding = info.get('sharesOutstanding')
        except Exception:
            pass

    for rec in records:
        rec_date_str = rec['date']
        rec_id = rec['id']

        if rec_date_str not in df.index:
            if not dry_run:
                _delete_records([rec])
            result['no_data'] += 1
            continue

        row_idx = df.index.get_loc(rec_date_str)
        if isinstance(row_idx, slice):
            row_idx = row_idx.start
        elif not isinstance(row_idx, (int, np.integer)):
            try:
                row_idx = int(row_idx[0])
            except Exception:
                row_idx = int(row_idx)

        today_row = df.iloc[row_idx]

        if row_idx == 0:
            if not dry_run:
                _delete_records([rec])
            result['no_data'] += 1
            continue

        prev_row = df.iloc[row_idx - 1]
        prev_close = float(prev_row['Close'])
        open_price = float(today_row['Open'])
        close_price = float(today_row['Close'])
        high_price = float(today_row['High'])
        low_price = float(today_row['Low'])
        volume = float(today_row['Volume'])

        if prev_close == 0:
            if not dry_run:
                _delete_records([rec])
            result['no_data'] += 1
            continue

        gap_pct = ((open_price - prev_close) / prev_close) * 100

        if gap_pct < MIN_REAL_GAP or gap_pct > MAX_REAL_GAP:
            if not dry_run:
                _delete_records([rec])
            result['deleted_bad_gap'] += 1
            continue

        start_window = max(0, row_idx - RVOL_WINDOW_DAYS)
        prior_slice = df.iloc[start_window:row_idx]
        avg_volume_val = float(prior_slice['Volume'].mean()) if len(prior_slice) > 0 else 0
        rvol = round(volume / avg_volume_val, 2) if avg_volume_val > 0 else None

        dollar_volume = round(close_price * volume, 0) if volume else None
        close_location = round((close_price - low_price) / (high_price - low_price), 3) if high_price > low_price else None

        rs_vs_spy = None
        if not spy_df.empty and rec_date_str in spy_df.index:
            try:
                spy_row = spy_df.loc[rec_date_str]
                if isinstance(spy_row, pd.DataFrame):
                    spy_row = spy_row.iloc[0]
                spy_open = float(spy_row['Open'])
                spy_close = float(spy_row['Close'])
                if spy_open > 0:
                    spy_return = ((spy_close - spy_open) / spy_open) * 100
                    rs_vs_spy = round(gap_pct - spy_return, 2)
            except Exception as e:
                log.debug(f"[{ticker}] Failed to calculate RS vs SPY: {e}")

        if dry_run:
            log.info(f"[DRY RUN] {ticker} {rec_date_str}: "
                     f"gap={gap_pct:.1f}% rvol={rvol} float={float_shares} sector={sector}")
            result['updated'] += 1
            continue

        with get_connection() as conn:
            conn.execute(
                """UPDATE daily_gainers
                   SET gap_pct             = %s,
                       float_shares        = %s,
                       rvol_15m            = %s,
                       sector              = %s,
                       market_cap          = %s,
                       open_price          = %s,
                       close_price         = %s,
                       high_price          = %s,
                       low_price           = %s,
                       prev_close          = %s,
                       dollar_volume       = %s,
                       close_location      = %s,
                       rs_vs_spy           = %s,
                       shares_outstanding  = %s,
                       avg_volume          = %s
                   WHERE id = %s""",
                (
                    round(gap_pct, 2),
                    float_shares,
                    rvol,
                    sector,
                    market_cap,
                    round(open_price, 4),
                    round(close_price, 4),
                    round(high_price, 4),
                    round(low_price, 4),
                    round(prev_close, 4),
                    dollar_volume,
                    close_location,
                    rs_vs_spy,
                    shares_outstanding,
                    round(avg_volume_val, 2) if avg_volume_val else None,
                    rec_id,
                )
            )
        result['updated'] += 1

    return result


def _yf_float_fallback(ticker: str) -> float | None:
    """
    Lightweight yfinance call for float shares only.
    Used exclusively as a fallback when FMP/Schwab returns None.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return info.get('floatShares') or info.get('sharesOutstanding')
    except Exception as e:
        log.debug(f"[{ticker}] yfinance float fallback failed: {e}")
        return None


def _delete_records(records: list[dict]):
    ids = [r['id'] for r in records]
    if not ids:
        return
    placeholders = ','.join(['%s'] * len(ids))
    with get_connection() as conn:
        conn.execute(
            f"DELETE FROM daily_gainers WHERE id IN ({placeholders})",
            ids
        )


if __name__ == '__main__':
    main()
