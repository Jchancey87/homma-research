import sys
import os

# Add backend and project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dotenv import load_dotenv
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

from database import get_connection

def main():
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE gap_pct >= 30) as gap_30_plus,
                    COUNT(*) FILTER (WHERE gap_pct >= 15 AND gap_pct < 30) as gap_15_to_30,
                    COUNT(*) FILTER (WHERE gap_pct >= 5 AND gap_pct < 15) as gap_5_to_15,
                    COUNT(*) as total
                FROM daily_gainers;
            """)
            row = cur.fetchone()
            print("Distribution of gap percentages in daily_gainers:")
            print(f"Gap >= 30%: {row['gap_30_plus']}")
            print(f"Gap 15% - 30%: {row['gap_15_to_30']}")
            print(f"Gap 5% - 15%: {row['gap_5_to_15']}")
            print(f"Total: {row['total']}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error querying database: {e}")

if __name__ == '__main__':
    main()
