# Agentic Memory & Reflections (`AGENT_MEMORY.md`) 🧠

This file acts as a persistent memory block where AI coding agents record prompt adaptations, debugging failures, architectural decisions, and key directives to prevent system drift across sessions.

---

## 🏛️ Chronological History of Learnings & Struggles

### [2026-06-06] backend - Concurrency Error Resilience & System Telegram Alerts

* **Struggle 1: Silent Background Failures**
  - *Context*: The background cache refresh thread previously froze silently because it had no timeout on `as_completed()` and lacked log traceback capturing and active alerting.
  - *Cause*: Swallowed exception tracebacks (`log.error(f"...: {e}")` without `exc_info=True`) made debugging difficult, and lack of real-time alerting meant the user was unaware the live screener stopped updating until hours later.
  - *Resolution*: Upgraded logs to use `log.exception(...)` to preserve full tracebacks. Added a synchronous Telegram messaging helper `send_telegram_message` to dispatch system warnings. Implemented rate-limited auth error notifications (once per hour) and consecutive failure tracking (alerting after 3 consecutive failures, sending recovery updates on success) in `_background_refresh_loop`.
* **Struggle 2: Redundant Concurrency Overhead on Authentication Failure**
  - *Context*: If Schwab auth fails (e.g. expired refresh token), the live screener was submitting 25 concurrent enrichment requests, all of which would individually attempt to load the client and throw exceptions.
  - *Cause*: `enrich_gainers_with_sparklines_and_history` was submitting tasks to the thread pool before checking if the Schwab client could be successfully initialized.
  - *Resolution*: Added a check to fail-early on Schwab client initialization failures, logging the issue once, sending a rate-limited system notification, and populating gainers with schema-compliant defaults immediately without overhead.

---

### [2026-06-05] backend & frontend - Alert Journal: Ingest Backfill & v5 Markers API

* **Struggle 1: SQL Comment-Filtering Bug in Migration Runner**
  - *Context*: Running the database migration via the custom `run_alerts_feedback_migration.py` script succeeded but left `feedback_score` missing from both tables, while `feedback_notes` was added successfully.
  - *Cause*: The script split the SQL file by `;` and filtered out statements starting with comments (`s.strip().startswith('--')`). Because the `feedback_score` statements had a comment line immediately preceding the SQL code (e.g., `-- Add feedback columns...`), the stripped string started with `--` and was completely skipped.
  - *Resolution*: Updated `run_alerts_feedback_migration.py` to strip out SQL comments line-by-line before splitting by `;`. Rerunning it successfully added the columns to the active database.
* **Struggle 2: Lightweight Charts v5 Markers Compilation Failure**
  - *Context*: Next.js build failed with: `Property 'setMarkers' does not exist on type 'ISeriesApi<"Candlestick", ...>'`.
  - *Cause*: In `lightweight-charts` version 5 (used by the frontend), the direct `.setMarkers()` method was removed in favor of the plugin-based primitive architecture.
  - *Resolution*: Imported the `createSeriesMarkers` plugin helper from `lightweight-charts` and updated the chart creation logic to use `createSeriesMarkers(candles, markers)` to draw the markers. The Next.js production build then compiled cleanly.

---

### [2026-05-19] backend/ - FastAPI Migration & Event Loop Issues
* **Struggle 1: Test Suite Hangs (Event Loop Mismatch)**
  * *Context*: Running `pytest` would hang indefinitely when initializing database pools.
  * *Cause*: Conflict between `anyio` and `pytest-asyncio` driving different loop scopes.
  * *Resolution*: Forced `pytest-asyncio` to own session-scoped loops and disabled anyio (`-p no:anyio` flag). Future test runs should always run async-native with `-p no:anyio`.
* **Struggle 2: asyncpg Strict Datatype Checks**
  * *Context*: watchlists and observations queries failed with `expected datetime instance, got str`.
  * *Cause*: `asyncpg` does not implicitly cast ISO-formatted strings to `TIMESTAMPTZ` columns in Postgres (unlike psycopg2 or sqlite).
  * *Resolution*: Always construct and pass python `datetime` objects directly rather than calling `.isoformat()` when working with `asyncpg` queries.
* **Struggle 3: Python Import Shadowing (`sys.path` Conflict)**
  * *Context*: `fastapi_app/main.py` failed to import configs properly.
  * *Cause*: Adding `fastapi_app/` to the front of `sys.path` shadowed `backend/config.py` with `fastapi_app/config.py` (which contains FastAPI `Settings`).
  * *Resolution*: Path bootstrappers in entry points must point to the parent `backend/` root directory instead of the sub-router folders.

---

### [2026-05-20] frontend/ - Webpage CORS & Route Resolution
* **Struggle: CORS Wildcard with Credentials Block**
  * *Context*: Browser console CORS blocks on client-side requests: `No Access-Control-Allow-Origin header is present...`
  * *Cause*: FastAPI's `CORSMiddleware` cannot use `allow_origins=["*"]` when `allow_credentials=True`.
  * *Resolution*: In [main.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/main.py), strip `*` from allowed origins and define `allow_origin_regex="https?://.*"` to echo back the requesting client origin.

---

### [2026-06-01] database - TimescaleDB Hypertables Schema Setup
* **Struggle: Hypertable Unique Constraints violation**
  * *Context*: Converting `screener_alerts` to a TimescaleDB hypertable failed.
  * *Cause*: In TimescaleDB, all unique constraints (including primary keys) must include the time partitioning column (`alert_time` in this case).
  * *Resolution*: Define PKs on hypertables as compound indexes (e.g. `PRIMARY KEY (id, alert_time)`). Never use a single `SERIAL PRIMARY KEY` on hypertable structures.

---

### [2026-06-02] frontend - Chart Timezones & Latency Bottlenecks
* **Struggle 1: Lightweight Charts Timezone Shift**
  * *Context*: Interactive detail charts rendered UTC times that mismatched the trader's desktop times.
  * *Cause*: TradingView Lightweight Charts default to rendering in UTC.
  * *Resolution*: Shift the raw UTC timestamps in the frontend components by the browser's local offset: `timestamp - (offset_minutes * 60)` and dynamically resolve timezone labels (e.g. CDT, EDT) in UI headers.
* **Struggle 2: Page Loading Latency Blockers**
  * *Context*: Navigating between dashboard tabs took up to 3.4 seconds due to blocking API lookups.
  * *Cause*: Demand-driven cache updates blocked thread execution, and watchlist updates queried Symbol details sequentially.
  * *Resolution*:
    1. Replaced sequential HTTP loops with Schwab's batch quotes endpoint (`level_one_equity_subs` / batch requests).
    2. Converted demand-driven cache updates to an off-thread background refresh daemon `live-screener-refresh` in [live_screener.py](file:///home/jackc/projects/homma-research/backend/services/live_screener.py#L46), dropping endpoint response latency to <10ms.

---

### [2026-06-03] backend & frontend - Breakout Alerts Throttling & UI Chimes

* **Struggle 1: Environment Pathing inside System Tests**
  * *Context*: Testing the Schwab streaming client changes failed with `ModuleNotFoundError: No module named 'schwab'`.
  * *Cause*: Running tests with the global standard `python3` command bypassed the production virtualenv libraries.
  * *Resolution*: Always run test scripts or debug checks using the virtualenv interpreter: `/opt/trading-journal/backend/venv/bin/python3`.
* **Struggle 2: Redis Client 0-Subscribers Mismatch**
  * *Context*: Publishing mock alerts to Redis showed `Delivered to 0 subscribers` even with the browser tab open.
  * *Cause*: The development workspace at `/home/jackc/projects/homma-research` is completely decoupled from the production deployment workspace at `/opt/trading-journal`. Edits must be committed, pulled to `/opt/trading-journal`, and built before changes take effect on the active servers.
* **Struggle 3: Capitalization Typo in Settings Loading**
  * *Context*: Dispatching live Telegram messages failed with `401 Unauthorized` because the API token had a trailing `0` in `.env` (`TELEGRAM_BOT_TOKEN0`).
  * *Resolution*: Fixed key name typo in `.env` and verified Telegram returns `200 OK` for the dispatch.
* **Struggle 4: Missing Live Candidate Ingestion & Redundant Multipliers**
  * *Context*: Telegram alarms were not being received for stock breakouts seen on the HOD scanner.
  * *Cause*:
    1. During the day, `daily_gainers` and `stock_fundamentals` tables were empty, so the Schwab websocket streamer only subscribed to static watchlist symbols.
    2. A bug in parsing the Schwab `get_instruments` API response (attempting `.get(sym)` on raw `{'instruments': [...]}`) caused the nightly fundamental ingestion job to fail to load fundamentals.
    3. An incorrect `* 1_000_000` multiplier in `sharesOutstanding` and `marketCap` caused stock floats to scale into trillions, failing the streamer's float filter.
  * *Resolution*:
    1. Updated candidates fetching to query the FastAPI `/api/gainers/live` endpoint dynamically.
    2. Added self-healing logic to query the Schwab API for fundamentals on-demand if missing in the DB.
    3. Corrected raw list parsing for `get_instruments`.
    4. Removed the redundant `* 1_000_000` multiplier.
    5. Expanded alert filters (price: $1.00-$30.00, float: < 100M).
* **Struggle 5: Breakout Alert Spam During Runs (Tick-by-Tick Alerts)**
  * *Context*: Ticker alerts fired constantly (sometimes multiple times per second) as a stock broke out and rose rapidly, resulting in Telegram alert spam.
  * *Cause*: The `should_fire_alert` logic allowed any breakout to bypass the lockout period if the current price exceeded the previous trigger price, leading to alerts on every uptick.
  * *Resolution*: Redefined `alerts.should_fire_alert` to enforce both a percentage-based threshold (default 3% price rise) AND a minimum time cooldown (default 2 minutes) during the lockout. If a ticker is locked out, it can only trigger another alert if it has gone up at least 3% since the last alert and at least 2 minutes have elapsed.

---

### [2026-06-03] frontend & backend - Click-to-Expand Screener & Detailed Intraday Sparklines

* **Struggle 1: Production Deployment Permission Denied**
  * *Context*: Running `git pull` inside `/opt/trading-journal` failed with `cannot open '.git/FETCH_HEAD': Permission denied`.
  * *Cause*: The production folder is owned by the `root` user, but the local agent commands run as user `jackc`.
  * *Resolution*: Run the deployment operations (such as pulls and `/home/jackc/projects/homma-research/deploy.sh`) using `sudo` to bypass permission checks.
* **Struggle 2: Component Performance & Re-render Overhead**
  * *Context*: Moving the mouse over the screener rows scheduled React state updates and timeouts, leading to high CPU usage and unnecessary list re-renders.
  * *Cause*: Mouseenter/mouseleave events on rows set the `hoveredTicker` state which was used to handle hover expansion.
  * *Resolution*: Removed hover event handlers entirely, allowing Tailwind CSS (`hover:bg-gray-850/40`) to handle stylistic hover transitions efficiently while React state handles the toggle-on-click interaction purely.

---

### [2026-06-03] frontend - Codebase Review with Fallow

* **Struggle: Running Fallow in Multi-Language Repositories**
  * *Context*: Running `npx fallow` from the repository root threw dependency warnings and missed package-level checks.
  * *Cause*: Fallow scans the directory it is run in. Since the repository root lacks a `package.json` and `node_modules` (which are nested in `frontend/`), it cannot trace dependency graphs correctly.
  * *Resolution*: Always run Fallow commands inside the `frontend/` directory (e.g., `npx fallow` inside `frontend/`) to enable full package resolution.
  * *Tool Interaction*: When executing `npx fallow` via background task runners, the tool may prompt `Ok to proceed? (y)`. We must monitor the output stream and use the `send_input` tool to provide confirmation (`y\n`).

---

### [2026-06-04] backend - Daily Recap Extended Day Gainers

* **Struggle: Sorting by regular session opening gap rather than total change**
  * *Context*: The daily analysis email was only sorting daily gainers by the regular hours opening gap `gap_pct`.
  * *Cause*: The database queries in `daily_analysis_report.py` and sorting logic in `ingest_gainers.py` were ordering by `gap_pct` rather than the total daily change (which at 8:05 PM includes post-market). Furthermore, `ingest_gainers.py` strictly filtered out tickers with `gap_pct < 5.0`, meaning intraday or post-market runners with flat opens were not recorded in `daily_gainers` at all.
  * *Resolution*: Added `extended_change_pct` to the database schema, updated `ingest_gainers.py` to calculate it using the latest last price, relaxed the pre-filter and final ingestion filters to allow tickers that qualify via either `gap_pct >= 5.0` OR `extended_change_pct >= 5.0`, sorted the ingestion list by `extended_change_pct`, and updated `daily_analysis_report.py` and `llm_client.py` to select, order, format, and display the gainers by `extended_change_pct`.

---

### [2026-06-04] backend - VWAP Crossover Hysteresis & Suppression

* **Struggle: VWAP crossover alert spam during consolidation**
  * *Context*: When a stock's price consolidated right around its VWAP, it triggered a massive cascade of VWAP crossover alerts.
  * *Cause*: The streaming client lacked a proper crossover state machine and simply fired alerts on any tick where `last_price > vwap` and `rvol >= 2.0`. When the 10-minute database cooldown expired, any subsequent tick still above VWAP fired a new alert immediately, even if the price had been above VWAP the whole time. Furthermore, minor price oscillations back and forth over the exact VWAP price line produced rapid crossover signals.
  * *Resolution*: Implemented a clean hysteresis state machine in `stream_client.py` using status states (`'above'` and `'below'`) and a `0.2%` price band buffer. The price must cross strictly above `vwap * 1.002` to trigger a crossover alert and set state to `'above'`, and it must drop below `vwap * 0.998` to reset state to `'below'`.

---

### [2026-06-04] devops & backend - Schwab OAuth Setup & VWAP Hysteresis Buffer Adjustment

* **Struggle 1: Schwab Token Expiration**
  * *Context*: The Schwab API health check failed with `invalid_grant` / `Refresh token is invalid, expired or revoked`.
  * *Cause*: The cached refresh token in `/home/jackc/.config/schwab/token.json` was generated 20 days prior and expired.
  * *Resolution*: Ran `schwab_auth_setup.py` in the background, extracted the manual OAuth URL, asked the user to authorize, and fed the redirected URL containing the auth code back to the script. The script saved the new token and the health check script passed successfully.
* **Struggle 2: Production Git Lock Permissions**
  * *Context*: Discarding local changes to `/opt/trading-journal/ecosystem.config.js` to allow a clean git pull failed with `Permission denied` to `.git/index.lock`.
  * *Cause*: The git repository files in production are owned by `root`, requiring sudo. However, running interactive `sudo` via agent background tasks prompts for a password and hangs.
  * *Resolution*: Pushed the synchronized config and code changes to remote from the developer workspace `/home/jackc/projects/homma-research`, and advised the user to execute the cleanup and deployment commands directly in their shell terminal.

### [2026-06-04] backend - Telegram Formatting & Watchlist-Only VWAP Alerts

* **Struggle 1: Direct link formatting in Telegram MarkdownV1**
  * *Context*: Tickers in Telegram alerts were plain text, making it tedious to open them in TradingView.
  * *Cause*: The Telegram Celery task didn't format tickers as hyperlinks.
  * *Resolution*: Updated `send_telegram_alert_task` in [alerts.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py) to format the stock ticker symbol as a Markdown link targeting `https://www.tradingview.com/chart/?symbol={symbol}`. Clicking it now opens the chart page, triggering the TradingView mobile/desktop app deep link handler.
* **Struggle 2: VWAP crossover alert noise on un-watched stocks**
  * *Context*: VWAP crossover alerts were still firing too frequently on general market runners, polluting the alert feed.
  * *Cause*: The streamer evaluated VWAP crossovers for all scanned candidates, rather than restricting it to high-interest tickers.
  * *Resolution*: Added an in-memory `self.watchlist_symbols` set to `SchwabStreamer`, updated dynamically via the 5-minute subscription sync loop query. Refactored the crossover trigger in [stream_client.py](file:///home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py) to check that the ticker is in this watchlist before firing a `VWAP_CROSSOVER` alert.

---

### [2026-06-04] backend - Momentum Alerts: Halts, Volume Spikes, Daily Breakouts, VWAP Bounces, & Gappers

* **Struggle 1: Tick boundary crossing volume calculation for 1-minute volume bars**
  * *Context*: 1-minute volume spikes failed to trigger because candle volume delta calculated from previous-tick values resulted in 0.
  * *Cause*: When the minute boundary changed, the previous candle was completed using `state['last_volume']` from the previous tick, which did not yet incorporate the boundary-crossing tick's volume.
  * *Resolution*: Updated the candle transition logic in `stream_client.py` to finalize the previous candle's close price and volume using the current boundary-crossing tick's data before calculating completed volume and resetting the candle state.
* **Struggle 2: Mocked test price range validation in unit tests**
  * *Context*: `test_vwap_bounce` and `test_prev_day_breakout` failed mock validation.
  * *Cause*:
    1. The mock price used for the VWAP bounce test ($101.50) fell outside the momentum filter price range ($1.00 - $30.00), preventing the alert from firing.
    2. The mock price used for the breakout test triggered the default HOD_BREAKOUT alert instead of the PREV_DAY_BREAKOUT alert because the high_price mock value was too low.
  * *Resolution*: Refactored tests to use prices inside the valid $1.00 - $30.00 range (e.g. VWAP = $10.00, bounce = $10.15) and set high_price mock values to a high ceiling ($30.00) to isolate tests from HOD_BREAKOUT triggers.

### [2026-06-05] backend - Live Gainer Screener Threshold Alignment & Gap Logic Fix

* **Struggle: Screener data not matching third-party live screeners during pre-market**
  * *Context*: The live gainers and Near HOD Radar dashboard displayed very few tickers, failing to match the user's reference screener.
  * *Cause*:
    1. The live screener's `MIN_GAP_PCT` was hardcoded to `30.0` (30% gap), far more restrictive than the nightly ingest job's `5.0` (5% gap).
    2. The live screener's `MAX_FLOAT_M` was set to `200.0` rather than the ingestion's `500.0`.
    3. In `_enrich_snapshot_tickers` (`live_screener.py`), the gap was evaluated against `t.get('todaysChangePerc')` (mapped to Schwab's `netPercentChange` which represents regular session change) *before* re-evaluating it against the live extended-hours price, causing pre-market gappers with low regular-session changes to be discarded prematurely.
  * *Resolution*:
    1. Aligned `MIN_GAP_PCT` to `5.0` and `MAX_FLOAT_M` to `500.0` in [live_screener.py](file:///home/jackc/projects/homma-research/backend/services/live_screener.py).
    2. Simplified `_enrich_snapshot_tickers` to compute the live gap percentage directly off the latest trade price and yesterday's close price in the first pass, bypassing dependency on the regular-session change field.

### [2026-06-05] frontend & backend - Live Screener Columns and Pre-Market ATR HOD Fix

* **Struggle 1: Pre-market ATR HOD showing 0.0**
  * *Context*: In the "Near HOD Radar" screener, the `AtrHoD` column showed all `0.0`s during pre-market.
  * *Cause*: Schwab Level 1 quote `highPrice` returns `0.0` during pre-market, which defaulted to the latest `last_price`. This made the calculated `hod` equal to `last_price` (`curr_p`), and therefore the ATR distance was `(last_price - last_price) / atr = 0.0`.
  * *Resolution*: Updated `get_minute_metrics()` in [live_screener.py](file:///home/jackc/projects/homma-research/backend/services/live_screener.py) to calculate the `hod` as the maximum of `high_price` (quote), `candle_high` (derived from the full pre-market 1-minute bars history in `candles`), and `curr_p`. This successfully preserves the pre-market HOD if price pulls back, and updates the gainer's `high_price` in the snapshot dynamically.
* **Struggle 2: Relative Volume Calculations Audit**
  * *Context*: Audited Schwab volume mapping for live Relative Volume calculations.
  * *Cause*: In pre-market, Schwab's Level 1 quote `totalVolume` can sometimes be `0` or `None`.
  * *Resolution*: Enhanced [schwab_client.py](file:///home/jackc/projects/homma-research/backend/services/schwab_client.py) quote mapping to fall back to the TradingView Amerika scanner's volume if Schwab's `totalVolume` is missing/0. Also added a fallback to `avg1YearVolume` if `avg10DaysVolume` is missing, ensuring a robust baseline for relative volume.
* **Struggle 3: Duplicate Identifier in API Types**
  * *Context*: Added `high_price` to `LiveGainerRow` interface in `lib/api.ts` but it caused a compilation error.
  * *Cause*: The interface already had `high_price?: number | null` declared at the bottom of the property list, which conflicted with the new declaration.
  * *Resolution*: Removed the duplicate declaration and verified the frontend compiles with zero TypeScript errors.

### [2026-06-05] backend - SMTP, Celery, and Schwab Client Thread-Safety

* **Struggle 1: Gmail SMTP Bad Credentials Failure**
  - *Context*: Nightly AI analysis reports failed to send by email.
  - *Cause*: The App Password specified in `.env` for `SMTP_PASSWORD` expired or was revoked, throwing `535 5.7.8 BadCredentials`.
  - *Resolution*: Audited credentials using `debug_email_status.py`, confirming failure in both development and production configs. Advised the user to generate a new Gmail App Password.
* **Struggle 2: Digital Garden Private IP Access Failure (SSRF)**
  - *Context*: Digital garden compilation failed with a security error when attempting to fetch from `192.168.0.202:5000`.
  - *Cause*: Cloud environment build runners block HTTP requests to RFC 1918 private IPs as an SSRF prevention measure.
  - *Resolution*: Identified Next.js proxy rewrite configuration `/api/*` forwarding to localhost. Advised the user to change the digital garden API target to `https://homma-research.homma.casa`.
* **Struggle 3: Celery worker ModuleNotFoundError**
  - *Context*: Async LLM tasks (`deep_context`, `catalyst_analysis`, etc.) failed with status `error`.
  - *Cause*: A dead import `from backend.routes.analysis import _CACHE_TTL` inside `llm_tasks.py` threw `ModuleNotFoundError` since the folder was renamed/refactored.
  - *Resolution*: Removed the obsolete import (since `_CACHE_TTL` is redefined locally on the next line). Verified by executing dry-run tests.
* **Struggle 4: Live Screener Thread Concurrency Socket Deadlock**
  - *Context*: During active market sessions, the live screener background refresh loop was supposed to update the cache every 60 seconds. However, it stopped updating completely and served stale morning data to the UI, causing the Schwab streamer to miss active after-hours runners (e.g. SCAG, GMHS, ELOG, BGMS, STI, etc.).
  - *Cause*: `live_screener.py` uses `ThreadPoolExecutor(max_workers=10)` to enrich multiple gainers in parallel. Each worker thread called `get_http_client()`, which returned a single shared `schwab.client.Client` instance wrapping a single `httpx.Client`. Since `httpx.Client` is *not thread-safe* for concurrent execution, concurrent requests from 10 threads corrupted the socket connection pool, leading to read operation timeouts and eventually deadlocking the sockets. All workers blocked indefinitely, freezing the background cache refresh loop.
  - *Resolution*: Modified `http_client.py`'s `get_http_client` to store and reuse Schwab Client instances inside `threading.local()`, ensuring thread-safety by providing a separate Client instance for each thread in the executor. Tested successfully with concurrent lookups.

---

## 📜 Central Directives for Future Agents

* **Environment Configuration**: Always verify environment variables in both the development workspace and the active production file [backend/.env](file:///home/jackc/projects/homma-research/backend/.env).
* **Database Cooldown Check**: The Schwab streaming client must query the PostgreSQL function `alerts.should_fire_alert` before publishing alerts to enforce ticker cooldowns and index-wide macro rate suppression. This function accepts `ALERT_MIN_PCT_INCREASE` (default 3% rise) and `ALERT_MIN_TIME_COOLDOWN_MINUTES` (default 2 mins) to suppress rapid-fire spam on running stocks during the active lockout.
* **No Raw Audio Asset Dependences**: Do not add raw sound files (`.wav`/`.mp3`) to the codebase for notification sounds. Use the browser-native Web Audio API `playPlinkChime` in [LiveGainers.tsx](file:///home/jackc/projects/homma-research/frontend/components/LiveGainers.tsx#L890) to synthesize sound chimes dynamically.
* **Production Deployment Flow**:
  1. Commit files locally in `/home/jackc/projects/homma-research`.
  2. Pull files on the server: `sudo git -C /opt/trading-journal/pull dev master` (or run deployment scripts).
  3. Rebuild/Restart using the deployment script: `sudo /opt/trading-journal/deploy.sh`.
* **Schwab Instrument API Parsing**: The Schwab API returns `{'instruments': [...]}` where instruments is a list. Mapped dictionary lookups (such as `.get(symbol)`) are not native; you must iterate and map the list into a dictionary keyed by symbol before attempting lookups.
* **Schwab Shares & Market Cap Units**: Schwab API returns absolute integers for `sharesOutstanding` and `marketCap`. Do not apply redundant `1,000,000` multipliers to them, as that will break float categorizations and filters.
* **Testing Infinite Event Streams**: When mocking infinite async generators (e.g. Redis pub/sub message loops in FastAPIs) for `pytest-asyncio` / `httpx.ASGITransport` tests, raise `asyncio.CancelledError` on termination rather than using long sleeps, preventing the test suite from hanging.
* **Detailed Intraday Sparkline Enrichment**: The live screener enriches snapshot gainers with a `sparkline_intraday` field containing downsampled (30 points) minute-close arrays. This is calculated dynamically inside `get_minute_metrics` and updated in real-time with the last trade price.
* **Toggle-on-Click Screener Details**: Screener detail rows in [LiveGainers.tsx](file:///home/jackc/projects/homma-research/frontend/components/LiveGainers.tsx) must only expand on explicit user click (`lockedTicker === g.ticker`). Avoid using React state for mouse hover interactions on large tables to prevent heavy UI lag.
* **Daily Gainers Ordering**: Daily gainers should be sorted and analyzed by `extended_change_pct` rather than `gap_pct` to capture the true total return (including pre-market, regular market, and post-market sessions).
* **VWAP Crossover State Machine**: To prevent alert chatter, VWAP crossovers must be evaluated using a hysteresis band (increased to $\pm 2.0\%$ buffer around VWAP by user request) and track discrete states (`'above'`/`'below'`) rather than checking raw inequality on every tick.
* **Watchlist-Restricted VWAP Crossover Alerts**: `VWAP_CROSSOVER` alerts in [stream_client.py](file:///home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py) must only trigger for ticker symbols that are currently present in the user's watchlist (`self.watchlist_symbols` set).
* **TradingView Ticker Hyperlinks**: All stock tickers in Telegram alert messages must be formatted as TradingView hyperlinks matching the format `[$TICKER](https://www.tradingview.com/chart/?symbol=TICKER)`.
* **Momentum Alert Types**: Keep in mind the new alert types: `VOLATILITY_HALT`, `VOLATILITY_RESUME`, `VOLUME_SPIKE`, `PREV_DAY_BREAKOUT`, and `VWAP_BOUNCE`. Make sure they follow the standard filters ($1-$30 price, <100M float) where applicable and trigger Telegram alerts.
* **Schwab HTTP Client Thread-Safety**: The Schwab HTTP client (`get_http_client()`) is stored in `threading.local()` to prevent concurrent HTTP requests on the same `httpx.Client` from deadlocking. Always use `get_http_client()` to obtain a thread-safe client instance. Do not store the client in global variables shared across concurrent threads.
