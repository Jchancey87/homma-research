"""
fastapi_app/db/core.py
Async database layer built on asyncpg.

Provides:
  - lifespan helpers (create_pool / close_pool) called by main.py
  - get_db() — FastAPI dependency that yields a connection from the pool
  - row_to_dict() / rows_to_list() — asyncpg Record → plain dict helpers
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg

from fastapi_app.config import settings

log = logging.getLogger(__name__)

# Module-level pool reference — set during app startup, cleared on shutdown.
_pool: asyncpg.Pool | None = None


# ---------------------------------------------------------------------------
# Pool lifecycle
# ---------------------------------------------------------------------------

async def create_pool() -> None:
    """Create the asyncpg connection pool.  Call once at startup."""
    global _pool
    log.info("[db] Creating asyncpg pool → %s", settings.asyncpg_dsn)
    _pool = await asyncpg.create_pool(
        dsn=settings.asyncpg_dsn,
        ssl=False,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    log.info("[db] Pool ready (%s min / %s max connections)", 2, 10)


async def close_pool() -> None:
    """Gracefully close the pool.  Call once at shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("[db] Pool closed")


def get_pool() -> asyncpg.Pool:
    """Return the active pool, raising RuntimeError if not initialised."""
    if _pool is None:
        raise RuntimeError("Database pool has not been initialised.  "
                           "Did lifespan / startup run?")
    return _pool


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Yield a connection from the pool.

    Usage in a route::

        @router.get("/example")
        async def example(db: asyncpg.Connection = Depends(get_db)):
            return await db.fetch("SELECT 1")
    """
    async with get_pool().acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def row_to_dict(record: asyncpg.Record | None) -> dict | None:
    """Convert a single asyncpg Record to a plain dict (or None)."""
    return dict(record) if record is not None else None


def rows_to_list(records: list[asyncpg.Record]) -> list[dict]:
    """Convert a list of asyncpg Records to a list of plain dicts."""
    return [dict(r) for r in records]


# ---------------------------------------------------------------------------
# Health helper
# ---------------------------------------------------------------------------

async def check_db_health() -> bool:
    """Return True if the pool can execute a trivial query."""
    try:
        async with get_pool().acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as exc:
        log.warning("[db] Health check failed: %s", exc)
        return False
