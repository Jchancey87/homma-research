import sys
import os
import pickle

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

backup_data = {}

print("Backing up database...")
for table in tables:
    try:
        with get_connection() as conn:
            cur = conn._conn.cursor()  # use raw connection cursor to inspect description
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            
            # Convert RealDictCursor rows to standard dicts
            rows_dict = [dict(r) for r in rows]
            backup_data[table] = rows_dict
            print(f"- {table}: backed up {len(rows_dict)} rows")
    except Exception as e:
        print(f"- {table}: FAILED ({e})")

backup_file = os.path.join(os.path.dirname(__file__), 'db_backup.pkl')
with open(backup_file, 'wb') as f:
    pickle.dump(backup_data, f)

print(f"Backup saved successfully to {backup_file}")
