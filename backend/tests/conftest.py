"""
tests/conftest.py
Async test infrastructure for the FastAPI layer (pytest-asyncio 1.x).

With asyncio_mode = auto and asyncio_default_fixture_loop_scope = session
in pytest.ini, all async fixtures and tests share ONE event loop per session.
This means the asyncpg pool (created in pool_lifecycle) is accessible to
every test without cross-loop errors.

Key design decisions that prevent hanging:
- lifespan="off" on the ASGITransport — APScheduler must NOT start during tests.
  The scheduler's AsyncIOScheduler tries to own its own event loop context and
  deadlocks when pytest-asyncio already owns the session loop.
- The get_db dependency is overridden to use the pool created by pool_lifecycle,
  so every route handler gets a real DB connection without going through lifespan.
"""
from __future__ import annotations

import os
import sys
import logging

import pytest_asyncio
import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ---------------------------------------------------------------------------
# Pool lifecycle — runs once per session, before any test that uses the pool
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session", autouse=True)
async def pool_lifecycle():
    """Create the asyncpg pool once; apply schema; tear down after all tests."""
    from fastapi_app.db import create_pool, close_pool, get_pool

    await create_pool()
    pool = get_pool()

    # Best-effort schema apply — ignore "already exists" errors
    schema_files = [
        os.path.join(_BACKEND_DIR, "models", "schema.sql"),
        os.path.join(os.path.dirname(_BACKEND_DIR), "momentum_screener", "db", "schema_schwab.sql"),
    ]
    combined = ""
    for path in schema_files:
        if os.path.exists(path):
            with open(path) as f:
                combined += f.read() + "\n"
    if combined:
        stmts = [s.strip() for s in combined.split(";") if s.strip()]
        async with pool.acquire() as conn:
            for stmt in stmts:
                try:
                    await conn.execute(stmt)
                except Exception as exc:
                    msg = str(exc)
                    if "already exists" not in msg and "duplicate" not in msg.lower():
                        log.warning("Schema stmt warning: %s", msg[:120])

    yield
    await close_pool()


# ---------------------------------------------------------------------------
# App fixture — lifespan disabled so APScheduler never starts
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def app(pool_lifecycle):
    """
    Return the FastAPI app with the get_db dependency overridden to use the
    pool that pool_lifecycle already created.  The ASGI lifespan is skipped
    (see client fixture) so APScheduler never runs during tests.
    """
    from fastapi_app.main import app as _app
    from fastapi_app.db import get_db, get_pool

    # Override get_db so routes use our already-running pool, not lifespan's
    async def _get_db_override():
        async with get_pool().acquire() as conn:
            yield conn

    _app.dependency_overrides[get_db] = _get_db_override
    yield _app
    _app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def client(app):
    """
    HTTPX AsyncClient bound to the FastAPI app.
    lifespan="off" prevents APScheduler from starting inside the pytest event
    loop (which would hang indefinitely).
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=True),
        base_url="http://testserver",
        timeout=30.0,
    ) as ac:
        yield ac
