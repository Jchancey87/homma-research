#!/usr/bin/env python3
import sys
import os

# Add parent path to import correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_connection

def run_migration():
    migration_path = os.path.join(os.path.dirname(__file__), '..', 'sql', 'alerts_feedback_migration.sql')
    print(f"Reading migration file: {migration_path}")
    with open(migration_path, 'r') as f:
        sql = f.read()

    # Clean SQL lines by removing comment lines
    clean_lines = []
    for line in sql.splitlines():
        if line.strip().startswith('--'):
            continue
        clean_lines.append(line)
    clean_sql = '\n'.join(clean_lines)

    # Split statements
    statements = [s.strip() for s in clean_sql.split(';') if s.strip()]

    print("Running migration statements...")
    with get_connection() as conn:
        for stmt in statements:
            if stmt.upper() in ('BEGIN', 'COMMIT'):
                continue
            print(f"Executing: {stmt[:60]}...")
            conn.execute(stmt)
    print("Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
