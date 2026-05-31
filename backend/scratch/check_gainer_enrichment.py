import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database import get_connection

query = """
SELECT ticker, date, premarket_high, premarket_volume, runway_months, dilution_risk 
FROM daily_gainers 
WHERE date = '2026-05-29' AND premarket_high IS NOT NULL;
"""

with get_connection() as conn:
    rows = conn.execute(query).fetchall()
    print(f"Found {len(rows)} enriched gainers on 2026-05-29:")
    for r in rows:
        print(dict(r))
