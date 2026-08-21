#!/usr/bin/env python3
"""
Backfill August 2026 daily gainers with full enrichment (fundamentals, catalysts, metrics).
"""
import os
import sys
import logging

_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import config
from jobs.ingest_gainers import fetch_gainers, write_gainers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger('backfill_august')

AUGUST_DATES = [
    '2026-08-03',
    '2026-08-04',
    '2026-08-05',
    '2026-08-06',
    '2026-08-07',
    '2026-08-10',
    '2026-08-11',
    '2026-08-12',
    '2026-08-13',
    '2026-08-17',
    '2026-08-18',
    '2026-08-19',
    '2026-08-20',
]

def main():
    log.info("Starting August 2026 backfill for %d trading days...", len(AUGUST_DATES))
    total_inserted = 0

    for d in AUGUST_DATES:
        log.info(f"=== Ingesting {d} ===")
        try:
            gainers = fetch_gainers(d)
            if gainers:
                inserted, skipped = write_gainers(gainers, d)
                log.info(f"[{d}] Ingested {len(gainers)} gainers (inserted/updated={inserted}, skipped={skipped})")
                total_inserted += inserted
            else:
                log.warning(f"[{d}] No gainers found")
        except Exception as e:
            log.error(f"[{d}] Failed to ingest: {e}", exc_info=True)

    log.info(f"August backfill complete! Total rows processed: {total_inserted}")

if __name__ == '__main__':
    main()
