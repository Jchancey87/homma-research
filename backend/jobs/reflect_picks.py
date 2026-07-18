#!/usr/bin/env python3
"""
Post-market reflection job.
Queries yesterday's continuation picks that have D1 outcomes,
runs the LLM reflection pass, and inserts the result to the DB.

Usage:
  python reflect_picks.py [--date 2026-05-01]
"""

import sys
import os
import argparse
import logging
import json
from datetime import datetime, timedelta

# Allow imports from backend/ and repo root
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from database import get_connection
from validation import EASTERN_TZ
from llm.llm_client import get_reflection

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Reflect on yesterday's continuation picks performance")
    eastern = EASTERN_TZ
    # Default is yesterday (date of picks), since today is when outcomes are populated.
    default_date = (datetime.now(eastern) - timedelta(days=1)).strftime('%Y-%m-%d')
    parser.add_argument('--date', default=default_date, help='YYYY-MM-DD date of the picks (normally yesterday)')
    args = parser.parse_args()

    target_date = args.date
    log.info(f"Starting reflection pass for picks on date {target_date}")

    # Query continuation picks for the target date where d1_close is not null
    query = """
        SELECT id, ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank,
               close_d0, d1_open, d1_high, d1_low, d1_close, d1_volume
        FROM continuation_picks
        WHERE date = %s AND d1_close IS NOT NULL
        ORDER BY rank ASC
    """
    with get_connection() as conn:
        rows = conn.execute(query, (target_date,)).fetchall()
        picks = [dict(r) for r in rows]

    if not picks:
        log.warning(f"No picks with D1 outcomes found in database for date {target_date}. Exiting.")
        return

    log.info(f"Found {len(picks)} picks with outcomes for date {target_date}. Running LLM reflection...")

    try:
        reflection_text, lessons = get_reflection(target_date, picks)
    except Exception as e:
        log.error(f"Failed to generate reflection from LLM: {e}")
        sys.exit(1)

    log.info("Reflection generated. Inserting into database...")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO continuation_reflections (date, reflection_text, lessons_json)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT (date) DO UPDATE
                SET reflection_text = EXCLUDED.reflection_text,
                    lessons_json = EXCLUDED.lessons_json,
                    created_at = CURRENT_TIMESTAMP
            """,
            (target_date, reflection_text, json.dumps(lessons))
        )

    log.info(f"Successfully saved reflection for {target_date} to database.")


if __name__ == '__main__':
    main()
