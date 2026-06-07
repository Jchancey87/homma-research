# Active Agent Memory & Decisions (`AGENT_MEMORY.md`) 🧠

This file maintains the active decisions, architectural constraints, and persistent principles that represent **what actually matters** for the project. 

> [!IMPORTANT]
> **Memory is not storage—it is training data for decisions.** 
> Stale rules are technical debt. Do not let them clutter our context.
> **Explicit Deletion/Pruning Permission**: You are explicitly authorized and encouraged to delete, modify, or prune sections of this file as soon as they become stale, resolved by clean code patterns, or no longer reflect the system's needs.

---

## 🌿 Branch: `main` (Persistent Core Decisions)

### 1. Schwab API Integration & Reliability
* **Thread-Safety for HTTP Client**: [get_http_client()](file:///home/jackc/projects/homma-research/momentum_screener/schwab/http_client.py) uses `threading.local()` to keep `httpx.Client` instances isolated per thread. Never store or share the Schwab HTTP client globally across concurrent threads to avoid socket deadlocks.
* **Instrument API Parsing**: Schwab API returns `{'instruments': [...]}` as a list. Convert/map this list into a dictionary keyed by symbol before attempting key-based lookups like `.get(symbol)`.
* **Shares & Market Cap Scale**: Schwab API returns absolute integers for `sharesOutstanding` and `marketCap`. Do not apply redundant `1,000,000` multipliers, otherwise float-based filters will fail.

### 2. Alert System & Hysteresis State Machine
* **Watchlist Constraint**: Breakout and momentum alerts (e.g. VWAP crossover) in [stream_client.py](file:///home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py) must only evaluate symbols actively in `self.watchlist_symbols` to prevent alerting noise.
* **VWAP Hysteresis**: Evaluate crossovers using a state machine (`'above'`/`'below'`) with a $\pm 2.0\%$ buffer (rather than simple inequalities) to prevent consolidation chatter.
* **Adaptive Cooldowns**: Verify cooldowns using the SQL function `alerts.should_fire_alert` before publishing. It enforces percentage-based thresholds (adaptive by price bucket, e.g. 2% to 8%) and time lockouts (2 mins) to suppress run spam.
* **Body-Close Confirmation**: HOD breakouts require a completed 1-minute candle close confirmation rather than raw tick highs to avoid false wick triggers.
* **Halt Suppression**: Suppress all momentum triggers for a symbol for 2 minutes following a volatility halt resume.

### 3. Frontend & UI performance
* **Toggle-on-Click Expand**: Large lists in [LiveGainers.tsx](file:///home/jackc/projects/homma-research/frontend/components/LiveGainers.tsx) must only expand details on explicit click. Avoid React state handlers on mouse hover/enter to prevent UI rendering lag.
* **Browser-Native Audio**: Synthesize chimes dynamically via the browser's Web Audio API (`playPlinkChime`). Do not bundle or download raw `.wav`/`.mp3` audio assets.
* **Detail Chart Centering**: Keep chart initializations and decorations split into separate hooks in [page.tsx](file:///home/jackc/projects/homma-research/frontend/app/alerts/page.tsx) to update indicators (markers, dashed trigger price line) without recreating the lightweight-charts instance.

### 4. Testing & Devops
* **Async Test Suite Execution**: Run test suites with `-p no:anyio` to let `pytest-asyncio` handle session-scoped event loops cleanly without hangs.
* **Infinite Event Streams Mocking**: Raise `asyncio.CancelledError` inside async generator loops to terminate tests instead of using long sleeps.
* **Production Deployment Flow**: Always run deployment operations using `sudo /opt/trading-journal/deploy.sh` since production paths are owned by the `root` user. Commit and push from developer workspace `/home/jackc/projects/homma-research` first.

---

## 🔱 Branch: `session` (Active Intent & Scope)

### Current Session: Continuation Play Journal & Performance Tracker
* **Goal**: Implement a multi-day continuation play journal and scorecard analyzer.
* **Forked context**: Inspected database schema for `continuation_picks` and frontend layout for `AlertsPerformance`.
* **Merged decisions**:
  - Rebuilt the `continuation_picks` schema to include D0 close, D1-D3 OHLCV, and fundamental fields (market cap, cash position, runway, dilution risk, catalyst status).
  - Created a robust async performance service (`continuation_performance_service.py`) with Schwab daily price bar integration and yfinance/FMP fallbacks.
  - Registered a nightly performance sync job in the scheduler and exposed manual force-update (`POST /refresh-performance`) and scorecard analytics (`GET /performance`) API endpoints.
  - Created a premium interactive Continuation Play Journal & Performance Tracker React dashboard (`frontend/app/continuation/page.tsx`) and added it to the NavBar.
* **Pruned context**: None.

---

## 🗑️ Rot & Pruning Log (Technical Debt Registry)
*Items listed here are marked for deletion or review next session if their underlying assumptions hold true.*
- *None currently listed.*
