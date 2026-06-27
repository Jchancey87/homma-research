import psycopg2
from psycopg2.extras import RealDictCursor
import json

def test_check_jobs():
    dsn = "postgres://journal:journal1@192.168.0.201:5432/trading_journal"
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get last 10 jobs
            cur.execute("""
                SELECT id, type, status, input_ref, model_used, created_at, updated_at, output
                FROM llm_jobs 
                ORDER BY created_at DESC 
                LIMIT 10;
            """)
            jobs = cur.fetchall()
            print("\nLATEST 10 JOBS:")
            for job in jobs:
                print(f"ID: {job['id']}")
                print(f"  Type: {job['type']}")
                print(f"  InputRef: {job['input_ref']}")
                print(f"  Status: {job['status']}")
                print(f"  Model: {job['model_used']}")
                print(f"  Created: {job['created_at']}")
                print(f"  Output (first 200 chars): {str(job['output'])[:200]}")
                print("-" * 40)
    finally:
        conn.close()
    assert True
