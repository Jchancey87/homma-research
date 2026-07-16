#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_connection

def run_migration():
    migration_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'alarm_management_migration.sql')
    print(f"Reading migration file: {migration_path}")
    with open(migration_path, 'r') as f:
        sql = f.read()

    print("Running migration against database...")
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    with get_connection() as conn:
        for stmt in statements:
            conn.execute(stmt)
    print("Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
