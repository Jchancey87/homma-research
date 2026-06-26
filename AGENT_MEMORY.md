# Active Agent Memory & Decisions (AGENT_MEMORY.md) 🧠

> ⚠️ STRICT CONSTRAINT: Keep under 500 tokens. Prune/delete stale info.

## 🌿 Branch: main (Persistent Core Decisions)

### 1. Schwab API & Data
* **Thread-Safety:** `get_http_client()` uses `threading.local()`. Never share client across threads.
* **Unified Candidate Pulling:** Primary source is Schwab Movers, fallback/enrich from TV, plus watchlists. Limit to 150. TV never overwrites Schwab unless its % change is strictly higher.
* **API Details:** Key Schwab `instruments` by symbol before lookups. `sharesOutstanding` and `marketCap` are absolute ints. Multiply `netPercentChange` by 100.
* **Live Quotes (RFC-004 QW-1):** All router-side batch quote fetching goes through `services.live_quotes_service.get_live_quotes(tickers, *, polygon_api_key=None)`. Returns `dict[ticker, NormalizedQuote]`. `NormalizedQuote` carries snake_case fields (`last_price`, `open_price`, `volume`, `change_pct`, `prev_close`, `source`). Routers MUST NOT import `get_quotes`/`get_ticker_snapshot`/raw `requests` for quote data.
* **Intraday Charts Cache Bypassing:** For today's date (or any future date), `get_chart_data` bypasses `price_history_1min` cached bars and queries live API (Schwab / fallbacks) to get the latest intraday candles, caching any new ones in DB via `ON CONFLICT DO NOTHING`. If live fetch fails, it falls back to DB bars.

### 2. Alerts & Hysteresis State Machine
* **Scope:** Evaluate symbols in `self.watchlist_symbols` only.
* **Triggers:** VWAP crossover uses hysteresis state ('above'/'below') ±2.0 buffer. HOD breakouts require 1-min body-close. Suppress triggers for 2 mins post-halt. Cooldowns use `alerts.should_fire_alert`.
* **Telegram format (RFC-004 QW-3):** `fastapi_app/tasks/alerts.py` builds messages via `_format_alert_message(alert_data)`. Header/signal/RVOL driven by `ALERT_TYPE_META: dict[str, dict]` at module top. Each value: `emoji`, `header`, `signal` (`None` | str | `"auto"` for dynamic-escape), `show_rvol` (bool). 7 known types + `FALLBACK_META` for unknown.

### 3. Live Screener & Momentum
* **Pipeline:** Flat 5-step flow in `live_screener.py`.
* **mom_2m:** Calculated relative to target 2m ago. If closest candle is >5m old, return `None`.
* **Caching & Sparklines:** 30s cache updates metrics inline. Daily cache holds 5d metrics. Flush caches on market session transitions. `sparkline_1h` caches last 60m of minute closes.
* **Filters:** MIN_GAP_PCT=5.0, MIN_PRICE=$0.50, MAX_PRICE=$100.
* **Polling:** Interval reduced 60s to 15s. cache_ttl_s = 15. Frontend main loop = 15s. "X ago" age label = 5s. Daily charts live refresh = 15s.

### 4. Validation Helpers (RFC-004 QW-4)
* **Ticker normalisation:** `from validation import normalize_ticker` — uppercase + strip. Replaces inline `ticker.upper().strip()`. Legacy `_upper_strip` alias kept in `validation/schemas.py` for in-module use only.
* **US/Eastern tz:** `from validation import EASTERN_TZ` — `pytz.timezone("America/New_York")` singleton. Replaces `pytz.timezone("US/Eastern")` and `pytz.timezone("America/New_York")` everywhere. APScheduler `CronTrigger(..., timezone=EASTERN_TZ)` and Celery `timezone=EASTERN_TZ` (object, not string). Test guard in `tests/test_validation_helpers.py` walks `backend/` and fails on rogue `pytz.timezone(...)` constructors.

### 5. db/ Module Convention (RFC-005)
* 7 new `db/` modules: `observations`, `charts`, `watchlist`, `market`, `screener_alerts`, `continuation_picks`, `daily_gainers`. Mirror `db/ohlcv.py` pattern.
* **Rule:** Every public function takes `conn: asyncpg.Connection` as the first positional arg. Returns plain dicts/lists/booleans (no `Record` leak).
* **Conventions:** `*_exists` returns `bool`. `update_*` accepts `dict` of column→value pairs and builds the SET clause internally. `delete_*`/`update_*` return `bool` from asyncpg's `"<n>"` status. `list_*` returns `list[dict]`. `get_*` returns `dict | None`.
* **7 audit routers** (observations, charts, watchlist, market, alerts, continuation, gainers) contain zero raw SQL. `routers/analysis.py` still has some on `llm_jobs`/`research_cache` — out of audit scope (already covered by RFC-001 chart_data_service).

### 8. Morning Scanner Scheduling (RFC-010)
* `momentum_screener/morning/scheduler.py::ScheduledTask(hour, minute, fn, *, name, tz=US/Central, weekdays_only=True, poll_seconds=30, now_fn=None)` — daily one-shot scheduler. Pure `should_run(now)` decision method (testable without threads); `_loop()` calls it in a daemon thread.
* `start()` is idempotent (lock-guarded `_thread` check). Original stubs violated this — calling `start()` twice spawned two threads.
* Errors in `fn` log + back off 60s; success polls every `poll_seconds`. `now_fn` injection point for tests.
* `premarket_gap.py` (22L) + `refresh.py` (22L) are now pure wiring (`ScheduledTask(8, 0, scan_gaps, name=...)` + `ScheduledTask(8, 45, run_full_refresh, name=...)`). All threading/time-sleep/last-run-date state lives in `scheduler.py`.

### 6. Frontend & UI
* **Interaction:** Toggle row expansion on click. No hover handlers.
* **Audio/Charts:** Dynamic chimes via Web Audio API. Split chart hooks (init vs decorators) in `page.tsx`.
* **TradeStation Style:** High density look. Matte black (#000000). Sharp 90deg edges (rounded-none). 1px charcoal grid gaps. Stark dotted canvas grid (#444444, style: 1). Neon series colors (bull #00ff00, bear #ff003c). Overlay HUD info (symbol, change %, EMA coordinates, volume color mapping) inside canvas to minimize vertical padding. Applied universally across all pages, NavBar, tables, details, badges, inputs.

### 7. Testing & DevOps
* **Venv Testing:** Execute backend tests using `/opt/trading-journal/backend/venv/bin/pytest`.
* **Async tests:** Run with `-p no:anyio` for clean asyncio loops.
* **Test surface:** 223 passing, 0 regressions. Started RFC-001 at 150; net +73 tests across all refactors.
* **Deploy:** Run `sudo /opt/trading-journal/deploy.sh` (push from `/home/jackc/projects/homma-research` first).

## 🔱 Branch: session (Active Intent & Scope)
* **Goal:** Fix blinking charts on daily chart overview during background poll.
* **Status:** Complete. Restricted loading overlay to initial mount. Implemented updating status indicator. Fixed GainerTable unescaped single quote.
* **Assumptions:** Users prefer background updates to be seamless without full-component blanking.

## 🗑️ Rot & Pruning Log
* RFC-001/002/003/004/005 + RFC-010 architectural refactor roadmap: COMPLETE. All decisions merged into main branch.
* Pruned QW-3/QW-4/RFC-005/RFC-010 active-intent entries.
* Applied Caveman Style rules.

