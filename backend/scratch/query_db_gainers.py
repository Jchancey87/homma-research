import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database import get_connection

with get_connection() as conn:
    rows = conn.execute("SELECT ticker, gap_pct, float_shares, rvol_15m, sector, news_headline, news_fresh, catalyst FROM daily_gainers WHERE date = '2026-05-27'").fetchall()
    print(f"Found {len(rows)} gainers on 2026-05-27:")
    for r in rows:
        print(r)
