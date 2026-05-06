import os
import psycopg2
import psycopg2.extras
from config import Config


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_connection():
    """Return a psycopg2 connection with RealDictCursor as the default cursor.

    Behaviour intentionally mirrors the old SQLite helper so every call-site
    that uses ``with get_connection() as conn:`` continues to work:
    - Entering the context manager returns the connection itself.
    - Exiting commits on success, rolls back on exception.
    - ``conn.execute(sql, params)`` returns a cursor whose rows support
      both index access (row[0]) and key access (row['col']), matching
      the old sqlite3.Row factory behaviour.
    """
    conn = psycopg2.connect(
        Config.DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn.autocommit = False
    return _ConnectionWrapper(conn)


class _ConnectionWrapper:
    """Thin wrapper that adds ``.execute()`` directly on the connection object,
    matching the sqlite3 ``conn.execute()`` shortcut."""

    def __init__(self, conn):
        self._conn = conn

    # ---- context-manager protocol ----------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        return False   # do not suppress exceptions

    # ---- forwarded helpers ------------------------------------------------

    def execute(self, sql: str, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Apply schema.sql on startup (idempotent — uses CREATE IF NOT EXISTS equivalents)."""
    schema_path = os.path.join(os.path.dirname(__file__), 'models', 'schema.sql')
    with open(schema_path, 'r') as f:
        schema = f.read()

    # Split on semicolons so each statement runs individually
    # (psycopg2 does not support executescript)
    statements = [s.strip() for s in schema.split(';') if s.strip()]
    with get_connection() as conn:
        for stmt in statements:
            conn.execute(stmt)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def get_db_status() -> bool:
    """Health-check: returns True if DB is reachable."""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
