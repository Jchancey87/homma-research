import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection

tables = [
    'daily_gainers',
    'chart_captures',
    'chart_tags',
    'llm_jobs',
    'watchlist',
    'continuation_picks',
    'observations',
    'pipe_filings',
    'research_cache'
]

print("Table Row Counts:")
for table in tables:
    try:
        with get_connection() as conn:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()['count']
            print(f"- {table}: {count}")
    except Exception as e:
        print(f"- {table}: ERROR ({e})")
