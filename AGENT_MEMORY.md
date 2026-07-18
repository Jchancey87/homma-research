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
* **Triggers:** VWAP crossover uses hysteresis state ('above'/'below') ±2.0 buffer. NEAR_HOD_RADAR breakout triggers on live price tick exceeding previous session high. VWAP_RECLAIM and HOD_BREAKOUT removed. Suppress triggers for 2 mins post-halt. Cooldowns use `alerts.should_fire_alert`.
* **Telegram format (RFC-004 QW-3):** [alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py) builds messages via `_format_alert_message(alert_data)`. Header/signal/RVOL driven by `ALERT_TYPE_META: dict` at module top. Each value: `emoji`, `header`, `signal`, `show_rvol`.

### 3. Live Screener & Momentum
* **Pipeline:** Two-tier refresh in `live_screener.py`. Fast path (2s): overlay WebSocket-streamed prices from `services/streaming_prices.py` (Redis `screener:quotes` channel) — zero REST calls. Slow path (60s): full 5-step pipeline (movers + quotes + enrichment). In `_fast_refresh()`, only overlays updates if streamed snapshot is strictly newer than the cached gainer row's last update (`_last_update_ts`), preventing stale websocket cache from reverting newer REST updates.
* **Streaming Bridge:** `StreamingPriceBridge` subscribes to Redis pub/sub in a daemon thread, maintains `_prices: dict[str, PriceSnapshot]` with 60s staleness expiry. `stream_client.py` caches Level 1 quote fields (`last_known_volume/high/low/open/bid/ask`), merging differential updates from Schwab WS, and publishes compact JSON ticks on every Level 1 quote.
* **mom_2m:** Calculated relative to target 2m ago. If closest candle is >5m old, return `None`.
* **Caching & Sparklines:** 30s minute-cache updates metrics inline. Daily cache holds 5d metrics. Flush caches on market session transitions. `sparkline_1h` caches last 60m of minute closes.
* **Filters:** MIN_GAP_PCT=5.0, MIN_PRICE=$0.50, MAX_PRICE=$100.
* **Polling:** FAST_REFRESH_SECONDS=2 (streaming), SLOW_REFRESH_SECONDS=60 (REST). CACHE_TTL_SECONDS=3 (frontend poll hint). /gainers/live returns redis_connected, fast_mode_active, and streaming_symbols_count. Both frontend daily-charts and LiveGainers poll at 3s and render status badges.
* **Subscription Loop:** `stream_client.py` uses `level_one_equity_add` for new symbols in `update_subscriptions`. Outdated `level_one_equity_subs` replaced all active subscriptions at Schwab.
* **Rank Change Indicators:** `GainerTable.tsx` tracks previous ranks via React state/ref. Computes rank shifts between polls, rendering green ChevronUp or red ChevronDown next to ticker. Removed FT and Speculative badges.
* **Decoupled Package (RFC-008):** `momentum_screener` has zero upward dependencies to `backend/config.py` or `backend/fastapi_app/celery_app.py`. Default `DATABASE_URL`, `ALERT_MIN_TIME_COOLDOWN_MINS` loaded from environment. Standalone Celery instance on local Redis broker replaces direct celery_app import.
* **Ross Scanners:** `live_screener.py` calculates pullbacks (`consec_red_1m`), 9 EMA distance (`ema9_dist_pct`), psychological half/whole dollar distance (`psych_dist_cents`), opening-rush volume ratio (`volume_ratio`), tape acceleration (`rvol_1m`), and daily space to nearest EMA/resistance (`nearest_resistance_dist`). Rendered in `GainerTable.tsx` depending on `scannerType`. Price sweet spot ($2-$10) and caution (<$2) ranges highlighted. Float unverified cells display pulsing `UNVERIFIED` and micro-floats (<5M) fuchsia. details drawer shows absolute `ATR (1m)` and `Spread (Cents)`.

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
* **TradeStation Style:** Redesigned visual system dark-mode dashboard. Preserve zero-round sharp edges. Map 4-level dark surface depth variables in `globals.css`: app background `#070A0D`, cards/panels `#0D1218`, nested/headers `#131B24`, hover states `#192431`. Unified colors via Tailwind config (`green-custom`, `red-custom`, `amber-custom`, `info-custom`). Applied `tabular-nums` universally for price, change, momentum, volume, float data columns. Added faint raised background containers to inline sparklines.
* **Continuation Journal:** Card-based UI grouped by date. Left colored border reflects tracking outcomes (Runner, Win, Flat, Fade, Active). Custom SVG inline sparklines show 3-day closes. Details pane opens inline. Scorecard metrics rendered as visual stacked percentage edge bars instead of static tables.
* **GainerTable Overhaul:** Columns reduced to 6: Rank, Ticker, Price, Change(%), Trend, Float. Rank always visible. Suffixes [RR]/[FT] as badges + tooltips in Ticker col. Price 16px, Rank 14px bold, Ticker 13px monospace, Change 14px bold, Float 12px. Float uses dot-badge + tooltip. Trend is emoji-badge + tooltip. Float cell includes expand chevron. Enabled SortKey trend sorting.


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

### 11. Alarm Management Overhaul (M1 & M2)
* **Database:** `alerts.alarm_metrics` table logs hourly/daily metrics rollups. Added `suppressed_reason`, `group_id` to `screener_alerts`, `screener_alerts_archive`.
* **Rollup Service:** `alarm_metrics_service.py` runs Celery task/real-time rollups. Tracks peak 10m rate, chattering, SNR, bad actors.
* **Grouping Correlation:** Group alerts on same symbol within 30s under shared UUID `group_id`.
* **Already In Play Suppression:** Suppress lower/equal priority alerts if Tier 1/2 already fired in session, unless price moves >5% from first alert. Saves to DB with reason `ALREADY_IN_PLAY`.
* **UI Journal Refactor:** Refactored alerts dashboard [page.tsx](file:///home/jackc/projects/homma-research/frontend/app/alerts/page.tsx) with EEMUA-aligned Alarm Health bar, sidebar sort, suppressed badges, Alarm Health view tab.

### 12. Watchlist Group & Enrichment
* **Segmentation:** Groups table segments biotech etfs (e.g. FDA approved vs trials). Scopes queries/imports/exports.
* **Enrichment:** Non-blocking `POST /enrich` runs in FastAPI `BackgroundTasks`. Fetches FMP/SEC/LLM metrics in parallel (`asyncio.to_thread`, semaphore=4) to prevent loop starvation. yfinance is completely removed. Dilution risk uses SEC XBRL shares history (`get_shares_history`) as primary. Falls back to SEC facts for cash/operating cash flows. Safely alerts Telegram if runway < 6 months or dilution high. Retains existing database values on api fetch failure.

### 13. State-Gated Pipeline (Idea 3)
* **StockState Dataclass:** Defined in [stock_state.py](file:///home/jackc/projects/homma-research/backend/services/stock_state.py) with gating rules based on stock status (active, suspended, restricted, watchlist_only) and is_active flag.
* **Gated Enrichment:** [watchlist_service.py](file:///home/jackc/projects/homma-research/backend/services/watchlist_service.py)'s `enrich_watchlist_fundamentals` accepts optional `state: StockState | None = None`. If state is provided and `should_enrich` returns False, skips enrichment and returns 0.

### 14. Database-Backed Reflection Loop (Idea 1)
* **Schema & Init:** `continuation_reflections` table stores reflections (id, date, text, lessons_json). Created via `init_reflections_table` in [watchlist.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/db/watchlist.py) on app startup.
* **Reflection Loop:** `get_reflection` inside [llm_client.py](file:///home/jackc/projects/homma-research/backend/llm/llm_client.py) queries fast model. Nightly job [reflect_picks.py](file:///home/jackc/projects/homma-research/backend/jobs/reflect_picks.py) updates DB. [daily_analysis_report.py](file:///home/jackc/projects/homma-research/backend/jobs/daily_analysis_report.py) prepends last 3 DB reflections to continuation prompt.

### 15. Selective Sentiment on Alerts (Idea 5)
* **Selective Sentiment:** [alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py) appends sentiment if news headlines exist within last 6 hours, else omits it. Sentiment parsed by `get_headline_sentiment` in [llm_client.py](file:///home/jackc/projects/homma-research/backend/llm/llm_client.py).

### 16. Threshold-Based Pre-Digestion (Idea 4)
* **Pre-Digestion Gating:** [llm_client.py](file:///home/jackc/projects/homma-research/backend/llm/llm_client.py) digests news and filings using fast model if count > 2, otherwise passes raw JSON directly to deep model.

### 17. Target-Ranked Debate (Idea 2)
* **Debate Gating:** [llm_client.py](file:///home/jackc/projects/homma-research/backend/llm/llm_client.py)'s `get_continuation_analysis` runs Bull/Bear debate loop (fast model) + Synthesis (deep model) only for tickers with `gap_pct` >= 15.0. Tickers < 15.0 bypass debate using single-pass deep model.

### 18. API & Caching Optimization
* **Decoupling Massive/Polygon:** Completely decoupled from Massive/Polygon news APIs. Removed `MassiveNewsSource` from default news aggregator in [news_aggregator.py](file:///home/jackc/projects/homma-research/backend/services/news_aggregator.py) and replaced `_get_polygon_news` with `_get_fmp_news` inside [catalyst_service.py](file:///home/jackc/projects/homma-research/backend/services/catalyst_service.py).
* **CIK Caching:** SEC CIK resolution (`get_cik_from_ticker`) caches mappings to `sec_cik_map.json` in `Config.STORAGE_PATH` with a 24-hour TTL, preventing redundant 4MB downloads.
* **FMP News Source:** `FMPNewsSource` integrated in [news_aggregator.py](file:///home/jackc/projects/homma-research/backend/services/news_aggregator.py) as the primary news source before yfinance scraper.


## 🔱 Branch: session (Active Intent & Scope)
* **Goal:** Implement Ross Cameron scanner improvements for: Float Sweet Spot (<5M), Distance to Daily EMAs (50/200), News Catalyst Tag, Consecutive Red Candles (Pullbacks), Distance to 9 EMA, Psychological Half/Whole dollar levels, Volume Ratio, Micro-bar RVOL, sweet spot highlighting, fallback float alert, and 20-cent risk metric.
* **Scope:** Modify live_screener.py, live_quotes_service.py, LiveGainers.tsx, GainerTable.tsx, badges.tsx, api.ts. Add calculated fields in backend, render layout with Ross rules in frontend.



## 🗑️ Rot & Pruning Log
* Pruned completed watchlist enrichment goals.



