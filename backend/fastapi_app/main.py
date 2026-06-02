"""
fastapi_app/main.py
FastAPI application entry point.

The lifespan context manager handles asyncpg pool creation/teardown and
APScheduler start/stop so both are ready before the first request lands.
"""
from __future__ import annotations

import logging
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncpg

# Ensure backend/ and the repo root (for momentum_screener) are in sys.path.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from .config import settings
from .db import create_pool, close_pool
from .scheduler import start_scheduler, stop_scheduler

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup → yield → shutdown."""
    log.info("[startup] Initialising asyncpg pool…")
    await create_pool()
    log.info("[startup] Starting APScheduler…")
    start_scheduler()
    log.info("[startup] FastAPI app ready on port 5000")
    yield
    log.info("[shutdown] Stopping APScheduler…")
    stop_scheduler()
    log.info("[shutdown] Closing asyncpg pool…")
    await close_pool()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=(
        "Homma Research async API"
    ),
    lifespan=lifespan,
)

# If allow_credentials is True, allow_origins cannot contain "*".
# We handle wildcard origins by using allow_origin_regex or parsing the request origin dynamically.
cors_origins = [o for o in settings.cors_origins if o != "*"]
allow_origin_regex = "https?://.*" if "*" in settings.cors_origins else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Built-in routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health():
    """Liveness + DB connectivity check — opens a fresh connection each call."""
    try:
        conn = await asyncpg.connect(
            dsn=settings.asyncpg_dsn,
            ssl=False,
            timeout=5,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "unreachable",
        "version": settings.app_version,
    }


@app.get("/", tags=["meta"])
async def root():
    return {"message": "Homma Research FastAPI — see /docs"}


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

# Phase 2 routers
from .routers import gainers, market
app.include_router(gainers.router, prefix="/api")
app.include_router(market.router,  prefix="/api")

# Phase 3 routers
from .routers import charts, watchlist, observations, continuation
app.include_router(charts.router,       prefix="/api")
app.include_router(watchlist.router,    prefix="/api")
app.include_router(observations.router, prefix="/api")
app.include_router(continuation.router, prefix="/api")

# Phase 4 routers
from .routers import analysis, alerts, market_data, strategies
app.include_router(analysis.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(market_data.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")

# Serve static storage files (charts, screenshots)
from fastapi.staticfiles import StaticFiles
storage_dir = os.path.dirname(settings.storage_path)
if os.path.exists(storage_dir):
    app.mount("/storage", StaticFiles(directory=storage_dir), name="storage")
else:
    log.warning(f"Static storage directory '{storage_dir}' does not exist. Serving disabled.")

