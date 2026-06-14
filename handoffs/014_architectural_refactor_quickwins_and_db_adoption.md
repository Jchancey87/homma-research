# ⚡ Handoff: RFC-004 Quick-Wins Batch + RFC-005 DB Module Adoption

Architectural refactor continuation. RFCs 001/002/003 complete; 150 tests pass; 0 regressions. This handoff covers the next 4 quick-wins + 1 major project.

---

## 📋 Context

**Done (RFC-001):** Extracted router business logic into 3 deep services + established Router Layer Rules in AGENTS.md §4. Routers slimmed by 585 lines. +58 unit tests.

**Done (RFC-002):** Deleted polygon shims. [schwab_client.py](file:///home/jackc/projects/homma-research/backend/services/schwab_client.py) is now single canonical Schwab import; re-exports all 8 upstream helpers + 9 legacy adapters. 10 callers migrated.

**Done (RFC-003):** Merged [backend/config.py](file:///home/jackc/projects/homma-research/backend/config.py) + [fastapi_app/config.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/config.py). Eliminated silent DATABASE_URL divergence (different password + host). [fastapi_app/config.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/config.py) is 2-line re-export. All 25 importer sites unchanged.

**Test surface:** 150 passing, 0 failures, 0 regressions across all 3 RFCs.

---

## 🚀 RFC-004: Quick-Wins Batch (~4h, ~250 lines removed)

### QW-1 — Build `services/live_quotes_service.py` (2h, ++ DRY)

**Problem:** 4 routers independently implement "try Schwab get_quotes, fall back to Polygon snapshot, then unwrap `quote.lastPrice`":
- [routers/continuation.py:54-72](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/continuation.py#L54) (adds 4 fields per row)
- [routers/watchlist.py:170-204](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/watchlist.py#L170) (adds price/chg_pct/volume)
- [routers/gainers.py:500-531](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/gainers.py#L500) (adds today_open/last/volume)
- [routers/market.py:77-125](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/market.py#L77) (adds price/chg_pct/volume per index)

Each does own `quotes[t].get('quote', {}).get('lastPrice')` shape unwrap.

**Plan:**
1. Create [services/live_quotes_service.py](file:///home/jackc/projects/homma-research/backend/services/live_quotes_service.py) with `async def get_live_quotes(tickers, db) -> dict[ticker, NormalizedQuote]`. Single function: Schwab chunk-of-50 → Polygon snapshot fallback for missing tickers → unwrap.
2. Add `tests/test_live_quotes_service.py` with mocks for `get_quotes` + `get_ticker_snapshot` covering: full coverage, partial, all-missing.
3. Migrate 4 routers to call service; delete inlined fallback chains.
4. **Verify:** `pytest tests/test_routers_timeseries.py tests/test_market.py tests/test_continuation.py tests/test_watchlist.py tests/test_gainers.py -p no:anyio` all pass.

### QW-2 — Unify chart-upload service (30m, ++ DRY)

**Problem:** [services/chart_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_service.py) (60L, Flask `FileStorage`) + [chart_service_shim.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/chart_service_shim.py) (79L, FastAPI `UploadFile`) contain byte-for-byte identical `validate_tags`, `save_chart_image`, `VALID_TAGS`. Differences: `mimetype`→`content_type`, `file.save()`→`open().write()`.

**Plan:**
1. Rewrite [services/chart_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_service.py) to accept minimal interface: `read_content() -> bytes`, `content_type: str`, `filename: str`. Add `save_chart_image(blob: bytes, content_type: str, filename: str) -> str`.
2. Update [charts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/charts.py) router to adapt `UploadFile` in 5 lines.
3. Delete [chart_service_shim.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/chart_service_shim.py).
4. **Verify:** `pytest tests/test_charts.py -p no:anyio` passes.

### QW-3 — Collapse 7 Telegram templates (30m, + DRY)

**Problem:** [tasks/alerts.py:158-243](file:///home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py#L158) has 7 `elif alert_type == "..."` branches (`VOLATILITY_HALT`, `VOLATILITY_RESUME`, `HOD_BREAKOUT`, `VOLUME_SPIKE`, `PREV_DAY_BREAKOUT`, `VWAP_CROSSOVER`, `VWAP_BOUNCE`). 85 lines differ only in header emoji/title + 2-3 optional field lines.

**Plan:**
1. Define `ALERT_TYPE_META: dict[str, dict]` at module top — keys: `header`, `emoji`, `extra_fields` (subset of {rvol, candle_vol, vwap, pdh, float}).
2. Replace 7 `elif` branches with `meta = ALERT_TYPE_META.get(alert_type, FALLBACK_META); header = f"{meta['emoji']} *{meta['header']}* {meta['emoji']}\n\n"` + f-string joining selected fields.
3. Keep `send_telegram_alert_task` signature; reduce body from 211 lines to ~80.
4. **Verify:** manual smoke test of each alert type or write `tests/test_alerts_telegram_format.py` with golden-message snapshots.

### QW-4 — Centralize `_upper_strip` + pick one TZ name (1h, + correctness)

**Problem:**
- `_upper_strip` helper exists in [validation/schemas.py:34-35](file:///home/jackc/projects/homma-research/backend/validation/schemas.py#L34) but bypassed by 18+ call sites that inline `ticker.upper().strip()`.
- TZ dual-spelling bug: `'US/Eastern'` (15+ sites in services/routers) vs `'America/New_York'` (8+ sites in routers/alerts.py + raw SQL in jobs/backfill_alert_candles.py). Same zone, two names — `pytz.utc.localize()` differs by 1h DST in some edge cases.

**Plan:**
1. Add to [validation/schemas.py](file:///home/jackc/projects/homma-research/backend/validation/schemas.py): `def normalize_ticker(s: str) -> str: return s.upper().strip()`. Export.
2. Add `EASTERN_TZ = pytz.timezone("America/New_York")` constant to [validation/schemas.py](file:///home/jackc/projects/homma-research/backend/validation/schemas.py) (or new `constants.py`).
3. Migrate 18+ ticker normalization call sites; pick canonical TZ, replace `'US/Eastern'` everywhere.
4. **Verify:** `grep -rn "US/Eastern\|America/New_York" backend/ --include="*.py"` returns 0 after migration. Pytest green.

---

## 🏗️ RFC-005: Adopt `db/` Module Pattern Across Remaining Routers (1-2d, ++++ testability)

**Problem:** 7 of 11 routers run raw SQL inline (bypasses [db/ohlcv.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/ohlcv.py), [db/strategies.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/strategies.py), [db/signals.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/signals.py), [db/indicators.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/indicators.py)). ~80 SQL strings total inside routers.

**Files affected** (from audit):
- [routers/charts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/charts.py) — 12 SQL strings on `chart_tags`, `chart_captures`
- [routers/observations.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/observations.py) — 8 on `observations`
- [routers/watchlist.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/watchlist.py) — 8 on `watchlist`
- [routers/continuation.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/continuation.py) — 8 on `continuation_picks` (SELECT only — INSERT/DELETE already done via `services.continuation_performance_service`)
- [routers/gainers.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/gainers.py) — 16 on `daily_gainers` (the biggest offender)
- [routers/alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/alerts.py) — 13 on `screener_alerts` (now mostly in service after RFC-001, but feedback + history still inline)
- [routers/market.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/market.py) — 3 on `daily_gainers`/`volatility_halts`

**Plan (per-router, 1-2h each):**
1. Create domain-specific `db/<table>.py` module mirroring [db/ohlcv.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/ohlcv.py) pattern (async functions, take `asyncpg.Connection` as first arg).
2. Move all SQL from router to module. Functions return plain dicts (or asyncpg Records — match existing pattern).
3. Router: `return await db_<table>.get_x(db, ...)` / `await db_<table>.insert_x(db, ...)`.
4. Add `tests/test_db_<table>.py` with async fixtures + rollback-transaction cleanup. Target: 3-5 tests per table CRUD.

**Suggested order (lowest risk first):**
1. [routers/observations.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/observations.py) (simplest table, 8 SQL) → 1h
2. [routers/charts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/charts.py) (12 SQL, includes upload) → 1.5h
3. [routers/watchlist.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/watchlist.py) (8 SQL) → 1h
4. [routers/market.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/market.py) (3 SQL) → 30m
5. [routers/alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/alerts.py) (13 SQL — feedback + history) → 1.5h
6. [routers/continuation.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/continuation.py) (8 SQL — list/stats) → 1h
7. [routers/gainers.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/gainers.py) (16 SQL — biggest) → 2h

**Verify after each:** `pytest tests/ -p no:anyio -q` green.

**End state:** All routers fully Router-Layer-Rules compliant (parse → call service → format). SQL never appears in router files.

---

## 🔭 Long-term (lower priority, do not start without explicit ask)

- **RFC-006:** Mirror Pydantic response models for frontend types in [lib/api.ts](file:///home/jackc/projects/homma-research/frontend/lib/api.ts) (31 interfaces) — 1d
- **RFC-007:** Migrate sync [database.py](file:///home/jackc/projects/homma-research/backend/database.py) → async stack (1-2w, large blast radius)
- **RFC-008:** Break `momentum_screener` → `backend` upward dependency ([stream_client.py:13-24](file:///home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py#L13)) — 1-2d
- **RFC-009:** Frontend: move hardcoded `API_BASE` + `fetch()` from [MiniSessionChart.tsx](file:///home/jackc/projects/homma-research/frontend/components/MiniSessionChart.tsx), [alerts/page.tsx](file:///home/jackc/projects/homma-research/frontend/app/alerts/page.tsx), [daily-charts/page.tsx](file:///home/jackc/projects/homma-research/frontend/app/daily-charts/page.tsx) into [lib/api.ts](file:///home/jackc/projects/homma-research/frontend/lib/api.ts) — 2h
- **RFC-010:** Replace morning scanner stubs in [momentum_screener/morning/premarket_gap.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/premarket_gap.py) + [refresh.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/refresh.py) with single `ScheduledTask(hour, minute, fn)` class — 1h

---

## 📁 Files created/modified by previous RFCs (reference)

**New services:**
- [chart_data_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_data_service.py) (354L)
- [alerts_analytics.py](file:///home/jackc/projects/homma-research/backend/services/alerts_analytics.py) (344L)
- [continuation_analytics.py](file:///home/jackc/projects/homma-research/backend/services/continuation_analytics.py) (187L)

**New tests (58 total):**
- [test_chart_data_service.py](file:///home/jackc/projects/homma-research/backend/tests/test_chart_data_service.py) (8 tests)
- [test_alerts_analytics.py](file:///home/jackc/projects/homma-research/backend/tests/test_alerts_analytics.py) (16 tests)
- [test_continuation_analytics.py](file:///home/jackc/projects/homma-research/backend/tests/test_continuation_analytics.py) (34 tests)

**Deleted:**
- [polygon_client.py](file:///home/jackc/projects/homma-research/backend/services/polygon_client.py) (22L shim)
- [polygon_service.py](file:///home/jackc/projects/homma-research/backend/services/polygon_service.py) (8L shim)

**Modified routers (slimmed):**
- analysis.py 528 → 307
- alerts.py 370 → 142
- continuation.py 283 → 147

---

## 🧪 Test Commands

```bash
# Full suite (150 tests, ~3 min)
cd backend && python3 -m pytest tests/ -p no:anyio -q

# Just new analytics unit tests (~1s each, no DB)
cd backend && python3 -m pytest tests/test_chart_data_service.py tests/test_alerts_analytics.py tests/test_continuation_analytics.py -p no:anyio

# Verify schwab facade is the only Schwab import path
grep -rn "from momentum_screener.schwab.http_client" backend/ --include="*.py" | grep -v services/schwab_client.py
# Expected: 0 results

# Verify config unification
python3 -c "from config import Config, settings; assert Config.DATABASE_URL == settings.database_url"
```

---

## ⚠️ Notes

- `schwab` Python package not in local env. Run `pip install --break-system-packages schwab-py` if `test_continuation.py::test_continuation_performance_and_refresh` fails on import. Pre-existing issue, not refactor-related.
- All env-var reading now goes through [backend/config.py](file:///home/jackc/projects/homma-research/backend/config.py) only. Any new env var should be added there in BOTH `Settings` (lowercase) and `Config` (UPPER_CASE) class bodies.
- Router Layer Rules ([AGENTS.md §4](file:///home/jackc/projects/homma-research/AGENTS.md)) now in effect — no new business logic in routers.
