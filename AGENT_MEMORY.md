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
* **Pipeline:** Two-tier refresh in `live_screener.py`. Fast path (2s): overlay WebSocket-streamed prices from `services/streaming_prices.py` (Redis `screener:quotes` channel) — zero REST calls. Slow path (60s): full 5-step pipeline (movers + quotes + enrichment).
* **Streaming Bridge:** `StreamingPriceBridge` subscribes to Redis pub/sub in a daemon thread, maintains `_prices: dict[str, PriceSnapshot]` with 60s staleness expiry. `stream_client.py` publishes compact JSON ticks on every Level 1 quote.
* **mom_2m:** Calculated relative to target 2m ago. If closest candle is >5m old, return `None`.
* **Caching & Sparklines:** 30s minute-cache updates metrics inline. Daily cache holds 5d metrics. Flush caches on market session transitions. `sparkline_1h` caches last 60m of minute closes.
* **Filters:** MIN_GAP_PCT=5.0, MIN_PRICE=$0.50, MAX_PRICE=$100.
* **Polling:** FAST_REFRESH_SECONDS=2 (streaming), SLOW_REFRESH_SECONDS=60 (REST). CACHE_TTL_SECONDS=3 (frontend poll hint). /gainers/live returns redis_connected, fast_mode_active, and streaming_symbols_count. Both frontend daily-charts and LiveGainers poll at 3s and render status badges.
* **Subscription Loop:** `stream_client.py` uses `level_one_equity_add` for new symbols in `update_subscriptions`. Outdated `level_one_equity_subs` replaced all active subscriptions at Schwab.
* **Rank Change Indicators:** `GainerTable.tsx` tracks previous ranks via React state/ref. Computes rank shifts between polls, rendering green ChevronUp or red ChevronDown next to ticker. Removed FT and Speculative badges.
* **Decoupled Package (RFC-008):** `momentum_screener` has zero upward dependencies to `backend/config.py` or `backend/fastapi_app/celery_app.py`. Default `DATABASE_URL`, `ALERT_MIN_TIME_COOLDOWN_MINS` loaded from environment. Standalone Celery instance on local Redis broker replaces direct celery_app import.

### 4. Validation Helpers (RFC-004 QW-4)
* **Ticker normalisation:** `from validation import normalize_ticker` — uppercase + strip. Replaces inline `ticker.upper().strip()`. Legacy `_upper_strip` alias kept in `validation/schemas.py` for in-module use only.
* **US/Eastern tz:** `from validation import EASTERN_TZ` — `pytz.timezone("America/New_York")` singleton. Replaces `pytz.timezone("US/Eastern")` and `pytz.timezone("America/New_York")` everywhere. APScheduler `CronTrigger(..., timezone=EASTERN_TZ)` and Celery `timezone=EASTERN_TZ` (object, not string). Test guard in `tests/test_validation_helpers.py` walks `backend/` and fails on rogue `pytz.timezone(...)` constructors.

### 5. db/ Module Convention (RFC-005)
* 8 `db/` modules: `observations`, `charts`, `watchlist`, `market`, `screener_alerts`, `continuation_picks`, `daily_gainers`, `rss`. Mirror `db/ohlcv.py` pattern.
* **Rule:** Every public function takes `conn: asyncpg.Connection` as the first positional arg. Returns plain dicts/lists/booleans (no `Record` leak).
* **Conventions:** `*_exists` returns `bool`. `update_*` accepts `dict` of column→value pairs and builds the SET clause internally. `delete_*`/`update_*` return `bool` from asyncpg's `"<n>"` status. `list_*` returns `list[dict]`. `get_*` returns `dict | None`.
* **8 audit routers** (observations, charts, watchlist, market, alerts, continuation, gainers, rss) contain zero raw SQL. `routers/analysis.py` still has some on `llm_jobs`/`research_cache` — out of audit scope (already covered by RFC-001 chart_data_service).

### 8. Morning Scanner Scheduling (RFC-010)
* `momentum_screener/morning/scheduler.py::ScheduledTask(hour, minute, fn, *, name, tz=US/Central, weekdays_only=True, poll_seconds=30, now_fn=None)` — daily one-shot scheduler. Pure `should_run(now)` decision method (testable without threads); `_loop()` calls it in a daemon thread.
* `start()` is idempotent (lock-guarded `_thread` check). Original stubs violated this — calling `start()` twice spawned two threads.
* Errors in `fn` log + back off 60s; success polls every `poll_seconds`. `now_fn` injection point for tests.
* `premarket_gap.py` (22L) + `refresh.py` (22L) are now pure wiring (`ScheduledTask(8, 0, scan_gaps, name=...)` + `ScheduledTask(8, 45, run_full_refresh, name=...)`). All threading/time-sleep/last-run-date state lives in `scheduler.py`.

### 6. Frontend & UI
* **Interaction:** Toggle row expansion on click. No hover handlers.
* **Audio/Charts:** Dynamic chimes via Web Audio API. Split chart hooks (init vs decorators) in `page.tsx`.
* **TradeStation Style:** High density look. Matte black (#000000). Sharp 90deg edges (rounded-none). 1px charcoal grid gaps. Stark dotted canvas grid (#444444, style: 1). Neon series colors (bull #00ff00, bear #ff003c). Overlay HUD info (symbol, change %, EMA coordinates, volume color mapping) inside canvas to minimize vertical padding. Applied universally across all pages, NavBar, tables, details, badges, inputs.
* **Continuation Journal:** Card-based UI grouped by date. Left colored border reflects tracking outcomes (Runner, Win, Flat, Fade, Active). Custom SVG inline sparklines show 3-day closes. Details pane opens inline. Scorecard metrics rendered as visual stacked percentage edge bars instead of static tables.

### 7. Testing & DevOps
* **Venv Testing:** Execute backend tests using `/opt/trading-journal/backend/venv/bin/pytest`.
* **Async tests:** Run with `-p no:anyio` for clean asyncio loops.
* **Test surface:** 264 passing, 0 regressions.
* **Deploy:** Run `/opt/trading-journal/deploy.sh` (push from `/home/jackc/projects/homma-research` first).
* **PYTHONPATH environment variable:** PM2 config ([ecosystem.config.js](file:///home/jackc/projects/homma-research/ecosystem.config.js)) specifies `PYTHONPATH` for Python/Celery worker/beat apps to prevent runtime `ModuleNotFoundError` inside spawned process contexts.

### 9. Optimization, Dashboards, and TimescaleDB Policies
* **Health Endpoint:** Uses `check_db_health` connection-pool based check.
* **Dashboard Overview:** Consolidated `/api/market/dashboard-overview` route gathers breadth, calendar, momentum, watchlist, and other dashboard data in parallel. Clean recursive `NaN` protection implemented.
* **TimescaleDB Compression Policy:** Enabled on `price_history_1min` hypertable for chunks older than 7 days.

### 10. RSS Curation System
* **RSS Ingestion & Curation:** Ingests active feeds every 15 mins (Job 7). Matches against target tickers (watchlist + daily gainers) using `stock_fundamentals` mapping to search for both cleaned company names and tickers. Restricts common/short words to strict regex patterns (requiring `$` or brackets/parentheses). Catalyst matches use regex word boundaries. Option B auto-approves if regulatory/catalyst keywords match. Remaining items staged in `rss_feed_pool` as `pending`.
* **Feed Generation:** Served at `/api/rss/feed` XML, dynamically enriched with live quotes (price, change, volume) via `live_quotes_service`.
* **Syndication:** Approved items sent to Telegram, truncated to 500 characters to fit API payload limits.
* **UI Manager:** Next.js `/rss` curation manager page styled in TradeStation matte black.

## 🔱 Branch: session (Active Intent & Scope)
* **Goal:** Troubleshoot deep ticker research.
* **Status:** Resolved. Celery worker process sys.path was missing `/opt/trading-journal/backend` under PM2 execution. Added PYTHONPATH to ecosystem.config.js and deployed. Tested TSLA research successfully via DeepSeek R1.
* **Actions:** Verified check_jobs.py database outputs showing completed status.

## 🗑️ Rot & Pruning Log
* Pruned old session goals.


