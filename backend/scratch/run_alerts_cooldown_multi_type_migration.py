#!/usr/bin/env python3
import sys
import os

# Add parent path to import correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_connection

def run_migration():
    migration_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'alerts_cooldown_multi_type.sql')
    print(f"Reading migration file: {migration_path}")
    with open(migration_path, 'r') as f:
        sql = f.read()

    print("Running migration against database...")
    with get_connection() as conn:
        conn.execute(sql)
    print("Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
