# FastAPI Migration — Phase 3 Handoff

## Status: Phases 1 & 2 Complete ✅

### What exists now
```
backend/
├── .env                          # DATABASE_URL + all secrets
├── pytest.ini                    # asyncio_mode=auto, asyncio_default_fixture_loop_scope=session
├── fastapi_app/
│   ├── __init__.py
│   ├── config.py                 # Settings dataclass, reads .env
│   ├── db.py                     # asyncpg pool (create_pool / close_pool / get_db / get_pool)
│   ├── main.py                   # FastAPI app, lifespan, CORS, /health, /
│   └── routers/
│       ├── __init__.py
│       ├── gainers.py            # Full async port of routes/gainers.py ✅
│       └── market.py             # Full async port of routes/market.py ✅
└── tests/
    ├── conftest.py               # session-scoped pool_lifecycle (autouse), client, db fixtures
    ├── test_health.py            # 4 tests ✅
    ├── test_gainers.py           # 10 tests ✅
    └── test_market.py            # 6 tests ✅
```

**Gate result:** `python3 -m pytest tests/ -v` → **20/20 passed**

---

## Database

- **Host:** 192.168.0.201 (Proxmox server)
- **Port:** 5432
- **DB:** trading_journal
- **User/Pass:** journal / journal1
- **SSL:** DISABLED — must pass `ssl=False` to asyncpg (server has md5 auth, no SSL cert)
- **Schema:** Applied manually. All tables exist. See `backend/models/schema.sql` for full schema.

### Critical DB notes
- asyncpg `ssl=False` is **required** — without it connections hang indefinitely (server has no SSL cert configured but doesn't fail fast)
- Standalone `asyncio.run()` scripts that try to connect tend to hang; always use the pytest pool or uvicorn for DB work
- The `journal` user needs `GRANT ALL ON SCHEMA public TO journal` (already done)
- Schema is idempotent (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`)

---

## Architecture Decisions (keep consistent in Phase 3)

1. **asyncpg pool** — singleton in `fastapi_app/db.py`, created at lifespan startup, `ssl=False, min_size=2, max_size=10`
2. **`get_db()` dependency** — `AsyncGenerator[asyncpg.Connection]` via `Depends(get_db)` for all route handlers
3. **`rows_to_list()` / `row_to_dict()`** — helpers in `db.py` to serialize asyncpg `Record` objects to plain dicts
4. **Router prefix pattern** — routers use their own prefix (`/gainers`, `/market`), app registers them under `/api`:
   ```python
   app.include_router(gainers.router, prefix="/api")
   app.include_router(market.router,  prefix="/api")
   ```
5. **Sync shims** — existing sync services (polygon_client, live_screener) are called via `asyncio.to_thread()` — do NOT call them directly in async handlers
6. **In-process caching** — `asyncio.Lock()` + dict for short-lived caches (TTL-based). Redis is a future Phase 4 concern.
7. **Config** — `fastapi_app/config.py` is self-contained (reads `.env` directly via `python-dotenv`). Do NOT import from `backend/config.py` to avoid circular imports.

---

## Remaining Flask Routes to Port (Phase 3)

Check `backend/routes/` for the full list. Priority order:

### High Priority
| Flask file | FastAPI target | Notes |
|---|---|---|
| `routes/charts.py` | `routers/charts.py` | Chart captures, Gemini annotation import, tag management |
| `routes/watchlist.py` | `routers/watchlist.py` | Ticker watchlist CRUD |
| `routes/observations.py` | `routers/observations.py` | Markdown notes per ticker |
| `routes/research.py` | `routers/research.py` | LLM research cache + job queue |

### Medium Priority
| Flask file | FastAPI target | Notes |
|---|---|---|
| `routes/pipe.py` | `routers/pipe.py` | PIPE filing detection cache |
| `routes/live.py` | `routers/live.py` | Live screener snapshot |
| `routes/continuation.py` | `routers/continuation.py` | AI continuation picks |

### Background Tasks (APScheduler)
Flask currently runs schedulers in-process. Phase 3 should migrate these to `apscheduler[asyncio]`:
- Nightly gainer ingest
- Continuation pick auto-expiry
- Research cache refresh

---

## Running the FastAPI App

```bash
# From backend/ directory:
uvicorn fastapi_app.main:app --port 8001 --reload

# Flask still runs on port 5000 (side-by-side during migration):
python app.py
```

## Running Tests

```bash
cd backend/
python3 -m pytest tests/ -v
```

---

## Known Issues / Gotchas

1. **`market/breadth` logs warnings** — `No module named 'momentum_screener'` when run from `backend/` dir. The endpoint gracefully returns `{"indices": {}, "bias": "unknown"}`. Fix by adding `momentum_screener/` to `sys.path` in `routers/market.py` or setting `PYTHONPATH`.
2. **Hanging `asyncio.run()` scripts** — connecting to Proxmox DB via standalone scripts tends to hang (SSL probe issue at the event loop level). Always test DB via pytest or uvicorn.
3. **`datetime.utcnow()` deprecation** — 4 warnings in gainers.py. Replace with `datetime.now(datetime.UTC)` in Phase 3 for cleanliness.
4. **`loop_scope="session"` on test marks** — tests are marked `@pytest.mark.asyncio(loop_scope="session")`. This is required for pytest-asyncio 1.x with the session pool.

---

## Phase 3 Goals

1. Port `charts`, `watchlist`, `observations`, `research`, `pipe`, `live`, `continuation` routers
2. Write corresponding tests for each router
3. Migrate background scheduler jobs to `apscheduler[asyncio]`
4. Phase 3 gate: all tests pass, manual smoke test comparing Flask vs FastAPI responses on key endpoints
5. Begin cutover planning — point frontend at port 8001
