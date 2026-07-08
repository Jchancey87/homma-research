import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'backend'))

from database import get_connection

def main():
    print("--- Watchlist Table ---")
    with get_connection() as conn:
        cur = conn.execute("SELECT ticker, sector, notes, tags FROM watchlist")
        rows = cur.fetchall()
        for r in rows:
            print(f"Ticker: {r['ticker']}, Sector: {r['sector']}, Tags: {r['tags']}, Notes: {r['notes']}")

if __name__ == '__main__':
    main()
