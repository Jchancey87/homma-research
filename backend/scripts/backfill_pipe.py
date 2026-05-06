#!/usr/bin/env python3
"""
backfill_pipe.py — Historical PIPE detection backfill script.

Scans all historical (ticker, date) pairs in daily_gainers for PIPE/private
placement 8-K filings filed within ±14 days of each gainer event date.
Results are cached in the pipe_filings table (skips already-scanned pairs).

Usage (from backend/):
    python scripts/backfill_pipe.py [--date YYYY-MM-DD] [--limit N] [--dry-run]

Options:
    --date      Only process a single specific date
    --limit     Max number of (ticker, date) pairs to process (default: all)
    --dry-run   Print what would be scanned without hitting EDGAR
    --min-gap   Only process gainers with gap_pct >= this value (default: 20.0)
"""
import sys
import time
import argparse
import logging

# Allow running from the backend/ directory
sys.path.insert(0, '.')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-7s  %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('backfill_pipe')


def parse_args():
    p = argparse.ArgumentParser(description='Backfill PIPE detection for historical gainers')
    p.add_argument('--date',    default=None,  help='Limit to a single date (YYYY-MM-DD)')
    p.add_argument('--limit',   default=None,  type=int, help='Max pairs to process')
    p.add_argument('--dry-run', action='store_true', help='Print plan without hitting EDGAR')
    p.add_argument('--min-gap', default=20.0,  type=float, help='Min gap_pct to include (default: 20.0)')
    return p.parse_args()


def get_pairs(date_filter=None, limit=None, min_gap=20.0):
    """
    Return all unique (ticker, date) pairs from daily_gainers, ordered by
    date DESC then gap_pct DESC (most recent high-gap events first).
    Excludes pairs already cached in pipe_filings.
    """
    from database import get_connection

    where_clauses = ['g.gap_pct >= %s']
    params        = [min_gap]

    if date_filter:
        where_clauses.append('g.date = %s')
        params.append(date_filter)

    where = 'WHERE ' + ' AND '.join(where_clauses)
    limit_clause = f'LIMIT {int(limit)}' if limit else ''

    sql = f"""
        SELECT g.ticker, g.date, g.gap_pct
        FROM   daily_gainers g
        LEFT JOIN pipe_filings p
               ON p.ticker = g.ticker AND p.anchor_date = g.date
        {where}
          AND p.id IS NULL          -- not yet scanned
        ORDER BY g.date DESC, g.gap_pct DESC
        {limit_clause}
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def main():
    args = parse_args()

    log.info('Loading database pairs…')
    pairs = get_pairs(
        date_filter=args.date,
        limit=args.limit,
        min_gap=args.min_gap,
    )

    if not pairs:
        log.info('Nothing to scan — all pairs already cached or no data found.')
        return

    log.info(f'Found {len(pairs)} (ticker, date) pairs to scan.')

    if args.dry_run:
        log.info('[DRY RUN] Would scan:')
        for p in pairs:
            log.info(f"  {p['ticker']:8s}  {p['date']}  gap={p['gap_pct']:.1f}%")
        return

    from services.pipe_service import detect_pipe_filing, _upsert_scan

    success = 0
    skipped = 0
    found   = 0
    errors  = 0

    for i, pair in enumerate(pairs, 1):
        ticker = pair['ticker']
        date   = pair['date']
        gap    = pair['gap_pct']

        log.info(f'[{i:4d}/{len(pairs)}]  {ticker:8s}  {date}  gap={gap:.1f}%')

        try:
            detection = detect_pipe_filing(
                ticker,
                anchor_date=date,
                days_back=14,
                days_forward=2,
            )
            _upsert_scan(ticker, date, detection)

            if detection['is_pipe']:
                score = detection.get('deal_score', '?')
                ptype = detection.get('pricing_type', '?')
                found += 1
                log.info(
                    f'         ✅ PIPE DETECTED  score={score}  pricing={ptype}'
                    f'  toxic_hits={len(detection.get("toxic_signals", []))}'
                )
            else:
                log.info(f'         ⬜ No PIPE filing within ±14 days')

            success += 1

        except Exception as e:
            errors += 1
            log.warning(f'         ❌ Error: {e}')

        # Small delay between tickers to be polite to EDGAR
        time.sleep(0.3)

    log.info('─' * 60)
    log.info(f'Done.  Processed={success}  PIPE detected={found}  Errors={errors}')


if __name__ == '__main__':
    main()
