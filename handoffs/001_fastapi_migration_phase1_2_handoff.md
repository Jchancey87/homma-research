# Handoff: Schwab Migration Completion & FastAPI Refactor Plan

## 1. Project Status Summary
The migration from Polygon.io to the **Schwab Trader API** is officially complete and functional. The backend now uses a "Shim" architecture to support legacy services while pulling real-time and historical data from Schwab. 

We have also just approved a plan to migrate the backend from **Flask to FastAPI** to better handle asynchronous I/O (especially for Schwab API calls and LLM jobs).

## 2. Completed: Schwab Migration
- **Client Layer**: `backend/services/schwab_client.py` is the new authority.
- **Shim Layer**: `backend/services/polygon_client.py` and `polygon_service.py` are now wrappers that delegate to the Schwab client.
- **Momentum Package**: New package `momentum_screener/` contains:
    - `schwab/`: Auth and HTTP clients.
    - `screener/`: Momentum filtering logic (Ross Cameron style).
    - `morning/`: Automated pre-market and morning refresh routines.
- **Database**: `db/schema_schwab.sql` has been implemented and is auto-applied on startup via `backend/database.py`.
- **Config**: `backend/config.py` now includes `SCHWAB_API_KEY`, `SCHWAB_API_SECRET`, and `SCHWAB_TOKEN_PATH`.

## 3. Approved Plan: FastAPI Migration (Phases 1 & 2)
The next session should focus on the first two phases of the FastAPI migration.

### Phase 1: Foundation
- **Goal**: Scaffolding and async database connectivity.
- **Key Files to Create**:
    - `backend/fastapi_app/main.py`: Entry point with `lifespan`.
    - `backend/fastapi_app/db.py`: `asyncpg` pool management.
    - `backend/tests/conftest.py`: Async testing infrastructure.
- **Dependencies**: `fastapi`, `uvicorn`, `asyncpg`, `pytest-asyncio`.

### Phase 2: Read-Only Routes
- **Goal**: Port `gainers.py` and `market.py` to FastAPI `APIRouter`.
- **Strategy**: Side-by-side execution. Run FastAPI on port 8001 while Flask stays on 8000 for verification.

## 4. Technical Context for Next Session
- **Environment**: Ensure `SCHWAB_API_KEY` and `SCHWAB_API_SECRET` are set.
- **Sudo Password**: `Lexus-Intent-7383` (needed for `pip install` in the venv).
- **Python Path**: The `momentum_screener` package is at the root. In `app.py`, we add `..` to `sys.path`. FastAPI will need similar consideration.
- **DB URL**: `asyncpg` requires a slightly different DSN prefix (`postgresql+asyncpg://`) if using SQLAlchemy, but for raw `asyncpg`, the standard `postgresql://` usually works depending on the driver usage.

## 5. Current Task List
The task tracker `task.md` is initialized and ready.
- [ ] Phase 1 Foundation (Scaffolding)
- [ ] Phase 2 Gainers/Market Porting

---
**Prepared by Antigravity**
**Date: 2026-05-16**
