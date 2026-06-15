# ⚡ Handoff: RFC-004 Quick-Wins Batch + RFC-005 DB Module Adoption

Architectural refactor continuation. RFCs 001/002/003 complete. This handoff covers the next 4 quick-wins + 1 major project.

**Status:** QW-1 ✅ · QW-2 ✅ · QW-3 ✅ · QW-4 ✅ · RFC-005 ✅ · RFC-010 ✅
**Test surface:** 241 passing, 0 failures, 0 regressions (started: 150; net +91 tests).

---

## 📋 Context

**Done (RFC-001):** Extracted router business logic into 3 deep services + established Router Layer Rules in AGENTS.md §4. Routers slimmed by 585 lines. +58 unit tests.

**Done (RFC-002):** Deleted polygon shims. [schwab_client.py](file:///home/jackc/projects/homma-research/backend/services/schwab_client.py) is now single canonical Schwab import; re-exports all 8 upstream helpers + 9 legacy adapters. 10 callers migrated.

**Done (RFC-003):** Merged [backend/config.py](file:///home/jackc/projects/homma-research/backend/config.py) + [fastapi_app/config.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/config.py). Eliminated silent DATABASE_URL divergence (different password + host). [fastapi_app/config.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/config.py) is 2-line re-export. All 25 importer sites unchanged.

**Done (QW-1):** Built [services/live_quotes_service.py](file:///home/jackc/projects/homma-research/backend/services/live_quotes_service.py) (249L). `async get_live_quotes(tickers, *, polygon_api_key=None) -> dict[ticker, NormalizedQuote]`. Schwab chunk-of-50 primary, per-ticker Polygon REST fallback. Pure helpers: `_quote_from_schwab`, `_quote_from_polygon`. Migrated 4 routers (continuation, watchlist, gainers, market). Routers slimmed by 114 lines. +24 unit tests. **Side-effect bonus:** market.py's "Polygon fallback" (which was a Schwab re-call post-RFC-002) is now a real Polygon REST fallback.

**Done (QW-2):** Rewrote [services/chart_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_service.py) (111L) to framework-agnostic `(blob, content_type, filename, *, ticker, capture_date, subfolder)` signature. Deleted [chart_service_shim.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/chart_service_shim.py) (-79L). [routers/charts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/charts.py) adapted 2 `UploadFile` call sites in 5-line `await image.read() + asyncio.to_thread(...)` blocks. +18 unit tests. Service is sync; routers wrap in `to_thread` for non-blocking I/O. **Discovery:** the old Flask `services/chart_service.py` had zero callers in the active codebase — safe to overwrite.

**Cumulative QW-1+QW-2:** +42 tests, 192 total, 0 regressions, -193 lines net across 5 routers + shim.

**Done (QW-3):** Collapsed 7 elif-branched Telegram alert templates into a single `ALERT_TYPE_META` lookup + unified `_format_alert_message` builder. See [QW-3 result section](#qw-3--collapse-7-telegram-templates-30m--drays) below.

**Done (QW-4):** Centralised `_upper_strip` as public `normalize_ticker` + added `EASTERN_TZ` constant. Migrated 18 inline `.upper().strip()` ticker-normalisation sites + 16 `pytz.timezone('US/Eastern'|'America/New_York')` callsites. See [QW-4 result section](#qw-4--centralize-_upper_strip--pick-one-tz-name-1h--correctness) below.

**Done (RFC-005):** All 7 routers in the audit now fully Router-Layer-Rules compliant. New `db/observations.py`, `db/charts.py`, `db/watchlist.py`, `db/market.py`, `db/screener_alerts.py`, `db/continuation_picks.py`, `db/daily_gainers.py` modules. ~80 SQL strings moved out of routers. See [RFC-005 result section](#-rfc-005-adopt-db-module-pattern-across-remaining-routers-1-2d--testability) below.

**Done (RFC-010):** Extracted the duplicated `_loop` + `start()` scaffolding from `momentum_screener/morning/{premarket_gap,refresh}.py` into a single `ScheduledTask(hour, minute, fn, *, name, tz, weekdays_only, poll_seconds, now_fn)` class. Pure `should_run(now)` decision method (testable without threads). `start()` is now idempotent. See [RFC-010 result section](#-rfc-010-scheduledtask-class-for-morning-scanners-1h--dry) below.

**Cumulative QW-1..4 + RFC-005 + RFC-010:** +91 tests, 241 total, 0 regressions.

---

## 🚀 RFC-004: Quick-Wins Batch (~4h, ~250 lines removed)

### QW-1 — Build `services/live_quotes_service.py` ✅ DONE (2h, ++ DRY)

**Problem:** 4 routers independently implement "try Schwab get_quotes, fall back to Polygon snapshot, then unwrap `quote.lastPrice`":
- [routers/continuation.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/continuation.py) (adds 4 fields per row)
- [routers/watchlist.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/watchlist.py) (adds price/chg_pct/volume)
- [routers/gainers.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/gainers.py) (adds today_open/last/volume)
- [routers/market.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/market.py) (adds price/chg_pct/volume per index)

**Result:**
- New: [services/live_quotes_service.py](file:///home/jackc/projects/homma-research/backend/services/live_quotes_service.py) (249L) + [tests/test_live_quotes_service.py](file:///home/jackc/projects/homma-research/backend/tests/test_live_quotes_service.py) (303L, 24 tests).
- Public surface: `get_live_quotes(tickers, *, polygon_api_key=None)` + `NormalizedQuote` dataclass (`last_price`, `open_price`, `volume`, `change_pct`, `prev_close`, `source`).
- Tickers de-duplicated case-insensitively; first-seen casing wins for result key.
- Missing tickers yield `NormalizedQuote(source="none", ...)` so callers do `nq.last_price` without null guards.
- Migration: routers slimmed by 114 lines total (continuation -9, watchlist -30, gainers -5, market -70).
- **Acceptance:** `pytest tests/ -p no:anyio` → 192/192 pass.

### QW-2 — Unify chart-upload service ✅ DONE (30m, ++ DRY)

**Problem:** [services/chart_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_service.py) (60L, Flask `FileStorage`, dead code) + [chart_service_shim.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/chart_service_shim.py) (79L, FastAPI `UploadFile`, the live path) had identical logic.

**Result:**
- Rewrote [services/chart_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_service.py) (111L) with framework-agnostic `save_chart_image(blob, content_type, filename, *, ticker, capture_date, subfolder) -> str`. Sync (blocking disk I/O); routers wrap in `asyncio.to_thread()`.
- New: [tests/test_chart_service.py](file:///home/jackc/projects/homma-research/backend/tests/test_chart_service.py) (173L, 18 tests). `tmp_path` + `monkeypatch.setattr("config.Config.STORAGE_PATH", ...)` for isolation.
- [routers/charts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/routers/charts.py) adapts 2 `UploadFile` call sites: `blob = await image.read(); image_path = await asyncio.to_thread(save_chart_image, blob, image.content_type or "", image.filename or "", ...)`.
- Deleted [chart_service_shim.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/chart_service_shim.py) (-79L).
- **Acceptance:** `pytest tests/ -p no:anyio` → 192/192 pass.

### QW-3 — Collapse 7 Telegram templates (30m, + DRY) ✅ DONE (~30m, ++ DRY)

**Problem:** [tasks/alerts.py:158-243](file:///home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py#L158) has 7 `elif alert_type == "..."` branches (`VOLATILITY_HALT`, `VOLATILITY_RESUME`, `HOD_BREAKOUT`, `VOLUME_SPIKE`, `PREV_DAY_BREAKOUT`, `VWAP_CROSSOVER`, `VWAP_BOUNCE`). 85 lines differ only in header emoji/title + 2-3 optional field lines.

**Result:**
- New module-level `ALERT_TYPE_META: dict[str, dict]` keyed by alert type. Each value: `emoji`, `header`, `signal` (`None` | static string | `"auto"`), `show_rvol` (bool).
- New `FALLBACK_META` for unknown alert types — renders generic header with dynamic, markdown-escaped signal.
- New `_format_alert_message(alert_data: dict) -> str` module-level function. Builds the full Markdown body via a single f-string assembly. Conditional lines (candle vol, vwap, pdh, float) self-guard as empty strings.
- Format helpers extracted to module level with `_` prefix: `_escape_markdown`, `_fmt_volume`, `_fmt_cap`, `_fmt_float`.
- `send_telegram_alert_task` body: 211 → 41 lines. File: 266 → 232 lines.
- New [tests/test_alerts_telegram_format.py](file:///home/jackc/projects/homma-research/backend/tests/test_alerts_telegram_format.py) (273L, 19 tests). Coverage: header + signal for all 7 known types, fallback dynamic-escape, sign handling (positive/negative/zero daily_pct), self-guarding optional fields, invalid timestamp passthrough, TV URL vs label escape, partial float/cap rendering, META dict contract (no silent type additions/removals).
- **Acceptance:** `pytest tests/ -p no:anyio` → 211/211 pass.
- **Side effect:** standardised field order across all types to `candle_vol → vwap → pdh → float` (was `candle_vol → pdh → vwap → float` for `PREV_DAY_BREAKOUT` only). Golden tests document the new order.

### QW-4 — Centralize `_upper_strip` + pick one TZ name (1h, + correctness) ✅ DONE (~45m, ++ correctness)

**Problem:**
- `_upper_strip` helper exists in [validation/schemas.py:34-35](file:///home/jackc/projects/homma-research/backend/validation/schemas.py#L34) but bypassed by 18+ call sites that inline `ticker.upper().strip()`.
- TZ dual-spelling bug: `'US/Eastern'` (15+ sites in services/routers) vs `'America/New_York'` (8+ sites in routers/alerts.py + raw SQL in jobs/backfill_alert_candles.py). Same zone, two names — every `pytz.timezone(...)` call creates a new `_DstTzInfo` instance, so two callers comparing `tz1 is tz2` would fail. Equality works but the objects are distinct.

**Result:**
- New [validation/constants.py](file:///home/jackc/projects/homma-research/backend/validation/constants.py) with `EASTERN_TZ = pytz.timezone("America/New_York")`.
- New public `normalize_ticker(v: str) -> str` in [validation/schemas.py](file:///home/jackc/projects/homma-research/backend/validation/schemas.py) (re-exported from [validation/__init__.py](file:///home/jackc/projects/homma-research/backend/validation/__init__.py) via `from validation import normalize_ticker, EASTERN_TZ`).
- Backwards-compat: `_upper_strip = normalize_ticker` alias so existing `field_validator` bodies don't need to change.
- Migrated 18 ticker-normalisation call sites across 8 files: routers/{charts, observations, watchlist, gainers, market_data}, db/signals, services/chart_data_service, jobs/daily_analysis_report. All now `from validation import normalize_ticker`.
- Migrated 16 `pytz.timezone('US/Eastern')` and `pytz.timezone('America/New_York')` Python callsites across 13 files (services, jobs, fastapi_app code). All now `from validation import EASTERN_TZ`.
- Updated 4 APScheduler `CronTrigger(..., timezone="US/Eastern")` and 1 Celery `timezone="US/Eastern"` to `timezone=EASTERN_TZ` (the object, not the string — typed and single-sourced).
- Cosmetic: comments mentioning "US/Eastern timezone" updated to "Eastern timezone" in 3 docstrings.
- New [tests/test_validation_helpers.py](file:///home/jackc/projects/homma-research/backend/tests/test_validation_helpers.py) (124L, 12 tests). Coverage: 6-case parametrised ticker normalisation, EASTERN_TZ identity (singleton), pytz `America/New_York` zone name, DST offset round-trip (EDT UTC-4 in June, EST UTC-5 in January), rogue `pytz.timezone('US/Eastern'|'America/New_York')` constructor guard (walks `backend/` and fails the test if any new caller sneaks in a constructor outside `validation/constants.py`).
- **Acceptance:** `grep -rn "US/Eastern" backend/ --include="*.py" | grep -v "validation/"` → 0 results. `grep -rn "pytz\.timezone" backend/ --include="*.py" | grep -v "validation/"` → 0 results. `pytest tests/ -p no:anyio` → 223/223 pass.
- **Note:** `America/New_York` still appears in raw SQL `AT TIME ZONE 'America/New_York'` (Postgres string API, not pytz) and in `pandas dt.tz_convert("America/New_York")` (pandas API). Both are string-typed and outside the scope of this normalisation.

---

## 🏗️ RFC-005: Adopt `db/` Module Pattern Across Remaining Routers (1-2d, ++++ testability) ✅ DONE (~3h total, ++++ testability)

**Problem:** 7 of 11 routers ran raw SQL inline (bypasses [db/ohlcv.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/ohlcv.py), [db/strategies.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/strategies.py), [db/signals.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/signals.py), [db/indicators.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/indicators.py)). ~80 SQL strings total inside routers.

**Result:** All 7 audit routers are now Router-Layer-Rules compliant. SQL never appears in any of them. 7 new `db/` modules created, mirroring the [db/ohlcv.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/ohlcv.py) pattern (async functions, `asyncpg.Connection` as first arg, return plain dicts/lists/booleans).

**New db/ modules:**
- [db/observations.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/observations.py) (145L) — `list_observations`, `list_observations_for_ticker`, `get_observation_by_id`, `create_observation`, `update_observation`, `delete_observation`.
- [db/charts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/charts.py) (192L) — `insert_chart_capture`, `update_chart_capture`, `update_gemini_import`, `delete_chart_capture`, `list_chart_captures`, `get_chart_capture`, `get_chart_capture_paths`, `sync_chart_tags`. Owns both `chart_captures` and `chart_tags` tables.
- [db/watchlist.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/watchlist.py) (95L) — `list_watchlist`, `list_watchlist_tickers`, `watchlist_ticker_exists`, `insert_watchlist`, `update_watchlist`, `mark_watchlist_viewed`, `delete_watchlist`.
- [db/market.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/market.py) (62L) — `latest_daily_gainers_date`, `top_rvol_float_on_date`, `active_volatility_halts_last_hour`.
- [db/screener_alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/screener_alerts.py) (85L) — `list_recent_alerts`, `list_alert_dates`, `save_alert_feedback` (writes to both `screener_alerts` + `screener_alerts_archive`).
- [db/continuation_picks.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/continuation_picks.py) (108L) — `list_picks`, `picks_stats_last_14_days`, `insert_pick`, `deactivate_pick`, `delete_pick`, `pick_exists`.
- [db/daily_gainers.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/daily_gainers.py) (290L, the largest) — shared `_filter_conditions` helper, `list_gainers`, `tickers_for_date`, `distinct_sectors`, `latest_ingest_summary`, `top_gainers_on_date`, `aggregate_ticker_history`, `list_appearances_for_ticker`, `aggregate_repeat_runners`, `bucket_gainers_by_float`, `sector_aggregates` (this-week / last-week), `previous_trading_date`, `top_gainers_for_follow_through`, `next_trading_day_for_ticker`.

**Per-router diffs (router line counts):**
- observations: 123 → 109 (-14)
- charts: 358 → 277 (-81; new helper structure makes the drop more visible)
- watchlist: 180 → 167 (-13)
- market: 443 → 432 (-11; small SQL surface, plus the in-process cache + helper code remains)
- alerts: 142 → 126 (-16)
- continuation: 138 → 118 (-20)
- gainers: 599 → 439 (-160, the biggest win)

**Architectural decisions:**
- Each db function returns `list[dict]`, `dict | None`, `bool`, `int`, or `Optional[date]`. No asyncpg `Record` objects leak past the module boundary.
- `*_exists` helpers return `bool` for the 404-check pattern; routers do `if not await db.x_exists(db, id): raise 404`.
- `update_*` helpers accept a `dict` of column→value pairs. They handle the dynamic SET-clause construction internally so the router stays one-liner-thin. Empty `updates` dict falls back to a `*_exists` check so PUT endpoints still return 404 on bogus IDs.
- `delete_*` / `update_*` return booleans from asyncpg's `"UPDATE <n>"` / `"DELETE <n>"` status string (true iff n > 0).
- Standardised param ordering: every db function takes `conn` as the first kwarg-by-position, then plain primitives, then optional filter kwargs. No `*args` or `**kwargs` magic.

**Acceptance:** `pytest tests/ -p no:anyio` → 223/223 pass. `grep -rn "fetchrow\|conn\.execute\|db\.fetch" backend/fastapi_app/routers/{alerts,charts,continuation,gainers,market,observations,watchlist}.py` → 0 matches. All 7 routers are Router-Layer-Rules compliant.

**Out of scope (intentionally left):**
- `routers/analysis.py` still has raw SQL on `llm_jobs` and `research_cache` tables. This was already covered by RFC-001 (chart_data_service extraction for the heavy analytics). Smaller LLM-job surface; not in the RFC-005 audit.
- `routers/market_data.py` and `routers/strategies.py` were already using the existing `db/ohlcv`, `db/indicators`, `db/strategies`, `db/signals` modules — no refactor needed.

**Future RFCs to consider:**
- Extend RFC-005 to `routers/analysis.py` (small: ~10 SQL strings on `llm_jobs` + `research_cache`).
- Add `tests/test_db_<table>.py` unit tests for each new db module (the existing `tests/test_<router>.py` integration tests already cover the surface, but dedicated db-layer tests would isolate SQL bugs from router-logic bugs).

---

## 🔭 Long-term (lower priority, do not start without explicit ask)

- **RFC-006:** Mirror Pydantic response models for frontend types in [lib/api.ts](file:///home/jackc/projects/homma-research/frontend/lib/api.ts) (31 interfaces) — 1d
- **RFC-007:** Migrate sync [database.py](file:///home/jackc/projects/homma-research/backend/database.py) → async stack (1-2w, large blast radius)
- **RFC-008:** Break `momentum_screener` → `backend` upward dependency ([stream_client.py:13-24](file:///home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py#L13)) — 1-2d
- **RFC-009:** Frontend: move hardcoded `API_BASE` + `fetch()` from [MiniSessionChart.tsx](file:///home/jackc/projects/homma-research/frontend/components/MiniSessionChart.tsx), [alerts/page.tsx](file:///home/jackc/projects/homma-research/frontend/app/alerts/page.tsx), [daily-charts/page.tsx](file:///home/jackc/projects/homma-research/frontend/app/daily-charts/page.tsx) into [lib/api.ts](file:///home/jackc/projects/homma-research/frontend/lib/api.ts) — 2h
- ~~**RFC-010:** Replace morning scanner stubs in [momentum_screener/morning/premarket_gap.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/premarket_gap.py) + [refresh.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/refresh.py) with single `ScheduledTask(hour, minute, fn)` class — 1h~~ ✅ DONE

---

## ⚡ RFC-010: ScheduledTask Class for Morning Scanners (1h, + DRY) ✅ DONE

**Problem:** [momentum_screener/morning/premarket_gap.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/premarket_gap.py) (51L, `PremarketGapScanner`) and [momentum_screener/morning/refresh.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/refresh.py) (57L, `MorningRoutine`) had byte-for-byte identical scaffolding: same `__init__` with `last_run_date = None`, same `start()` factory, same `_loop()` (weekday gate + hour:minute check + once-per-day guard), same `time.sleep(30)` polling, same `time.sleep(60)` error backoff, same `pytz.timezone('US/Central')` module-level constant. Two near-identical 50-line classes differing only in (hour, minute, fn) and the log message.

**Result:**
- New [momentum_screener/morning/scheduler.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/scheduler.py) (102L). `ScheduledTask(hour, minute, fn, *, name, tz="US/Central", weekdays_only=True, poll_seconds=30, now_fn=None)`.
  - `should_run(now: datetime | None = None) -> bool` — **pure decision method**. Returns True iff (a) weekday gate passes, (b) `now.hour:now.minute` matches, (c) hasn't already fired today. Side effect on fire: records today's date.
  - `_loop()` — 8-line daemon-thread wrapper. `try: should_run() → fn() / except: log + sleep 60s / continue: sleep poll_seconds`. Errors don't update `last_run_date` (next poll retries).
  - `start()` — **idempotent**. Lock-guarded `_thread` check; subsequent calls are no-ops. Original stubs violated this (two `start()` calls = two threads).
  - `now_fn` injection point for tests. tz accepts string OR object; string gets resolved through `pytz.timezone(...)` internally.
- [momentum_screener/morning/premarket_gap.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/premarket_gap.py) 51 → 22 (-29L). Pure wiring: `ScheduledTask(8, 0, scan_gaps, name="premarket-gap-scanner")` + `start_premarket_scanner()` factory.
- [momentum_screener/morning/refresh.py](file:///home/jackc/projects/homma-research/momentum_screener/morning/refresh.py) 57 → 22 (-35L). Pure wiring: `ScheduledTask(8, 45, run_full_refresh, name="morning-routine")` + `start_morning_routine()` factory.
- New [backend/tests/test_scheduled_task.py](file:///home/jackc/projects/homma-research/backend/tests/test_scheduled_task.py) (181L, 18 tests). Coverage: constructor validation (4 cases — hour/minute/fn/poll_seconds), defaults match legacy stubs, `should_run` happy path, off-minute no-fire, wrong-hour no-fire, once-per-day guard, next-day re-fire, weekday gate (Sat/Sun blocked by default), `weekdays_only=False` override, `now_fn` injection, tz string + object acceptance, `start()` idempotency (monkeypatched `threading.Thread` factory asserts exactly 1 instance across N calls).
- **Acceptance:** `pytest tests/ -p no:anyio -q` → 241/241 pass (was 223; +18). `grep -rn "threading\.Thread\|time\.sleep\|last_run_date" momentum_screener/morning/` → 7 matches, all in `scheduler.py`. Public API (`start_premarket_scanner`, `start_morning_routine`) unchanged.

**Architectural decisions:**
- `should_run(now)` is the **testable seam**. The entire firing decision (weekday gate + time match + once-per-day) is unit-testable in microseconds without sleeping, without threads, without the event loop. Threading is a 8-line wrapper.
- `start()` idempotency is a **new contract** the original stubs violated. Lock-guarded; `monkeypatch` test asserts exactly one `Thread` instance across N calls.
- `now_fn` injection point: tests pass `MagicMock(return_value=frozen_datetime)`; production uses `lambda: datetime.now(self.tz)`. No real-clock dependency in tests.
- tz accepts string OR object. String resolved via `pytz.timezone(...)` internally — keeps call sites simple (`tz="America/New_York"`) while preserving singleton identity if the canonical object is passed in.
- Error path: `time.sleep(60)` after exception (matches legacy), `time.sleep(poll_seconds)` on the normal path. `fn` failure does NOT update `last_run_date` — next poll retries the same minute.

**Out of scope (intentionally):**
- The morning routine body itself is still a stub (`log.info` only). The refactor de-risks the **wiring shape**; the body implementation is a separate task. Call sites (`scan_gaps`, `run_full_refresh`) preserve the original log messages.
- Central/Eastern tz normalisation: `validation.EASTERN_TZ` covers `America/New_York`; Central has no equivalent helper. The single `pytz.timezone("US/Central")` in `scheduler.py` is the module-level default for the morning routines (which run in CT, not ET). If a 2nd Central-tz call site appears, mirror the `EASTERN_TZ` pattern.

---

## 📁 Files created/modified by all RFCs (reference)

### RFC-001/002/003 (already complete)
**New services:**
- [chart_data_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_data_service.py) (354L)
- [alerts_analytics.py](file:///home/jackc/projects/homma-research/backend/services/alerts_analytics.py) (344L)
- [continuation_analytics.py](file:///home/jackc/projects/homma-research/backend/services/continuation_analytics.py) (187L)

**New tests (58 total):**
- test_chart_data_service.py (8)
- test_alerts_analytics.py (16)
- test_continuation_analytics.py (34)

**Deleted:**
- polygon_client.py (22L shim)
- polygon_service.py (8L shim)

**Modified routers (slimmed):**
- analysis.py 528 → 307
- alerts.py 370 → 142
- continuation.py 283 → 147

### QW-1 (done)
**New:**
- [services/live_quotes_service.py](file:///home/jackc/projects/homma-research/backend/services/live_quotes_service.py) (249L)
- [tests/test_live_quotes_service.py](file:///home/jackc/projects/homma-research/backend/tests/test_live_quotes_service.py) (303L, 24 tests)

**Modified routers:** continuation (-9), watchlist (-30), gainers (-5), market (-70). Total: -114L.

### QW-2 (done)
**Modified:**
- [services/chart_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_service.py) rewritten (60L Flask → 111L framework-agnostic)

**New:**
- [tests/test_chart_service.py](file:///home/jackc/projects/homma-research/backend/tests/test_chart_service.py) (173L, 18 tests)

**Modified router:** charts.py adapted 2 `UploadFile` call sites.

**Deleted:**
- fastapi_app/chart_service_shim.py (79L)

### QW-3 (done)
**Modified:**
- [fastapi_app/tasks/alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py) (266 → 232L). Module-level `ALERT_TYPE_META` dict + `_format_alert_message` builder. 7 elif branches → 1 f-string assembly.

**New:**
- [tests/test_alerts_telegram_format.py](file:///home/jackc/projects/homma-research/backend/tests/test_alerts_telegram_format.py) (273L, 19 tests). Golden-message snapshots for all 7 types + fallback.

### QW-4 (done)
**New:**
- [validation/constants.py](file:///home/jackc/projects/homma-research/backend/validation/constants.py) — `EASTERN_TZ` canonical tz.
- [tests/test_validation_helpers.py](file:///home/jackc/projects/homma-research/backend/tests/test_validation_helpers.py) (124L, 12 tests). Includes a self-walking grep guard against rogue `pytz.timezone(...)` calls.

**Modified:**
- [validation/schemas.py](file:///home/jackc/projects/homma-research/backend/validation/schemas.py) — added public `normalize_ticker` (re-export of `_upper_strip`).
- [validation/__init__.py](file:///home/jackc/projects/homma-research/backend/validation/__init__.py) — re-exports `normalize_ticker` and `EASTERN_TZ`.
- 13 files migrated: 18 ticker-normalisation sites + 16 `pytz.timezone(...)` callsites + 4 APScheduler + 1 Celery config.

### RFC-005 (done)
**New db/ modules** (7):
- [db/observations.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/observations.py) (145L)
- [db/charts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/charts.py) (192L)
- [db/watchlist.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/watchlist.py) (95L)
- [db/market.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/market.py) (62L)
- [db/screener_alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/screener_alerts.py) (85L)
- [db/continuation_picks.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/continuation_picks.py) (108L)
- [db/daily_gainers.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/daily_gainers.py) (290L)

**Modified routers (Router-Layer-Rules compliant):**
- observations: 123 → 109 (-14)
- charts: 358 → 277 (-81)
- watchlist: 180 → 167 (-13)
- market: 443 → 432 (-11)
- alerts: 142 → 126 (-16)
- continuation: 138 → 118 (-20)
- gainers: 599 → 439 (-160)

**Net:** ~80 SQL strings extracted from routers. All 7 routers now contain zero raw SQL / `db.execute` / `db.fetch` calls.

---

## 🧪 Test Commands

```bash
# Full suite (241 tests, ~3 min)
cd backend && /opt/trading-journal/backend/venv/bin/pytest tests/ -p no:anyio -q

# New QW-1..4 + RFC-005 + RFC-010 unit tests (~1s each, no DB)
cd backend && /opt/trading-journal/backend/venv/bin/pytest \
  tests/test_live_quotes_service.py \
  tests/test_chart_service.py \
  tests/test_alerts_telegram_format.py \
  tests/test_validation_helpers.py \
  tests/test_scheduled_task.py \
  -p no:anyio

# Verify Router-Layer-Rules compliance for the 7 RFC-005 routers
grep -rn "fetchrow\|conn\.execute\|db\.fetch" \
  backend/fastapi_app/routers/observations.py \
  backend/fastapi_app/routers/charts.py \
  backend/fastapi_app/routers/watchlist.py \
  backend/fastapi_app/routers/market.py \
  backend/fastapi_app/routers/alerts.py \
  backend/fastapi_app/routers/continuation.py \
  backend/fastapi_app/routers/gainers.py
# Expected: 0 matches

# Verify no rogue pytz.timezone('US/Eastern'|'America/New_York') construction
grep -rn "pytz\.timezone(['\"]\(US/Eastern\|America/New_York\)" backend/ --include="*.py" | grep -v "validation/"
# Expected: 0 results

# Verify no inline .upper().strip() in active code
grep -rn "\.upper()\.strip()" backend/ --include="*.py" | grep -v "/scratch/" | grep -v "validation/schemas"
# Expected: 0 results

# Verify no chart_service_shim references
grep -rn "chart_service_shim" backend/ --include="*.py"
# Expected: 0 results

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
- Ticker normalisation canonical name: `from validation import normalize_ticker`. Use it everywhere instead of inline `ticker.upper().strip()`. The legacy private alias `_upper_strip` in [validation/schemas.py](file:///home/jackc/projects/homma-research/backend/validation/schemas.py) is kept for in-module use only.
- US/Eastern tz canonical name: `from validation import EASTERN_TZ`. Use it instead of `pytz.timezone("US/Eastern")` or `pytz.timezone("America/New_York")` anywhere. The pytz object is a singleton — `EASTERN_TZ is EASTERN_TZ` returns True. Postpones the long-term `zoneinfo` migration.
- New db/ modules: 7 new files in [fastapi_app/db/](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/) following the existing `db/ohlcv.py` pattern. Routers depend on these via `from ..db import <table> as db_<table>` (NOT direct SQL). All public db functions take `asyncpg.Connection` as the first positional arg.
