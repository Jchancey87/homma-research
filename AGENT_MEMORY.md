# Agentic Memory & Reflections (`AGENT_MEMORY.md`) 🧠

This file acts as a persistent memory block where AI coding agents record prompt adaptations, debugging failures, architectural decisions, and key directives to prevent system drift across sessions.

---

## 🏛️ Chronological History of Learnings & Struggles

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

---

## 📜 Central Directives for Future Agents

* **Environment Configuration**: Always verify environment variables in both the development workspace and the active production file [backend/.env](file:///home/jackc/projects/homma-research/backend/.env).
* **Database Cooldown Check**: The Schwab streaming client must query the PostgreSQL function `alerts.should_fire_alert` before publishing alerts to enforce ticker cooldowns and index-wide macro rate suppression.
* **No Raw Audio Asset Dependences**: Do not add raw sound files (`.wav`/`.mp3`) to the codebase for notification sounds. Use the browser-native Web Audio API `playPlinkChime` in [LiveGainers.tsx](file:///home/jackc/projects/homma-research/frontend/components/LiveGainers.tsx#L890) to synthesize sound chimes dynamically.
* **Production Deployment Flow**:
  1. Commit files locally in `/home/jackc/projects/homma-research`.
  2. Pull files on the server: `sudo git -C /opt/trading-journal pull dev master`.
  3. Rebuild/Restart using the deployment script: `sudo /opt/trading-journal/deploy.sh`.
* **Schwab Instrument API Parsing**: The Schwab API returns `{'instruments': [...]}` where instruments is a list. Mapped dictionary lookups (such as `.get(symbol)`) are not native; you must iterate and map the list into a dictionary keyed by symbol before attempting lookups.
* **Schwab Shares & Market Cap Units**: Schwab API returns absolute integers for `sharesOutstanding` and `marketCap`. Do not apply redundant `1,000,000` multipliers to them, as that will break float categorizations and filters.
* **Testing Infinite Event Streams**: When mocking infinite async generators (e.g. Redis pub/sub message loops in FastAPIs) for `pytest-asyncio` / `httpx.ASGITransport` tests, raise `asyncio.CancelledError` on termination rather than using long sleeps, preventing the test suite from hanging.
