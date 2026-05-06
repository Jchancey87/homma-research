"""
migrate_tags.py — One-time (idempotent) migration of chart_captures.tags JSON strings
into the chart_tags junction table.

Run from the backend/ directory:
    python scripts/migrate_tags.py

Safe to run multiple times — uses ON CONFLICT DO NOTHING.
"""
import json
import sys
import os

# Allow running from backend/ or scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_connection


def migrate():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, tags FROM chart_captures WHERE tags IS NOT NULL AND tags != '[]'"
        ).fetchall()

        inserted = 0
        skipped  = 0

        for row in rows:
            chart_id  = row['id']
            tags_raw  = row['tags']
            try:
                tags = json.loads(tags_raw)
                if not isinstance(tags, list):
                    skipped += 1
                    continue
            except Exception:
                print(f"  [WARN] chart_id={chart_id}: could not parse tags JSON: {tags_raw!r}")
                skipped += 1
                continue

            for tag in tags:
                tag = str(tag).strip()
                if not tag:
                    continue
                try:
                    conn.execute(
                        "INSERT INTO chart_tags (chart_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (chart_id, tag),
                    )
                    inserted += 1
                except Exception as e:
                    print(f"  [ERROR] chart_id={chart_id} tag={tag!r}: {e}")

        print(f"Migration complete: {inserted} tag rows inserted, {skipped} rows skipped.")


if __name__ == '__main__':
    migrate()
