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
* **Unified Candidate Pulling**: [get_gainers_snapshot](file:///home/jackc/projects/homma-research/backend/services/schwab_client.py) merges TradingView candidates, Schwab Movers (NASDAQ, NYSE, and EQUITY_ALL), and user watchlist tickers. It sorts and trims to the top 150 candidates, always prioritizing all watchlist tickers first.
* **Schwab Movers API Mapping**: Schwab Movers API response uses camelCase keys (e.g. `lastPrice`, `netPercentChange`, `volume`) and fractional changes (e.g. `0.6246` for `62.46%`). Multiply `netPercentChange` by 100 to convert to a percentage.

### 2. Alert System & Hysteresis State Machine
* **Watchlist Constraint**: Breakout and momentum alerts (e.g. VWAP crossover) in [stream_client.py](file:///home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py) must only evaluate symbols actively in `self.watchlist_symbols` to prevent alerting noise.
* **VWAP Hysteresis**: Evaluate crossovers using a state machine (`'above'`/`'below'`) with a $\pm 2.0\%$ buffer (rather than simple inequalities) to prevent consolidation chatter.
* **Adaptive Cooldowns**: Verify cooldowns using the SQL function `alerts.should_fire_alert` before publishing. It enforces percentage-based thresholds (adaptive by price bucket, e.g. 2% to 8%) and time lockouts (2 mins) to suppress run spam.
* **Body-Close Confirmation**: HOD breakouts require a completed 1-minute candle close confirmation rather than raw tick highs to avoid false wick triggers.
* **Halt Suppression**: Suppress all momentum triggers for a symbol for 2 minutes following a volatility halt resume.

### 3. Live Screener & Momentum Calculations
* **Timestamp-Based Lookback**: Compute `mom_2m` in [live_screener.py](file:///home/jackc/projects/homma-research/backend/services/live_screener.py) by looking back for a candle at or before 2 minutes ago relative to the latest candle timestamp (rather than raw index indexing like `candles[-3]`) to handle low-volume/pre-market periods.
* **Dynamic Cache Recalculation**: Cache `price_2min_ago` in memory and dynamically update `mom_2m` within the 30-second cache window whenever a new `last_price` quote arrives, keeping the UI value responsive.

### 4. Frontend & UI performance
* **Toggle-on-Click Expand**: Large lists in [LiveGainers.tsx](file:///home/jackc/projects/homma-research/frontend/components/LiveGainers.tsx) must only expand details on explicit click. Avoid React state handlers on mouse hover/enter to prevent UI rendering lag.
* **Browser-Native Audio**: Synthesize chimes dynamically via the browser's Web Audio API (`playPlinkChime`). Do not bundle or download raw `.wav`/`.mp3` audio assets.
* **Detail Chart Centering**: Keep chart initializations and decorations split into separate hooks in [page.tsx](file:///home/jackc/projects/homma-research/frontend/app/alerts/page.tsx) to update indicators (markers, dashed trigger price line) without recreating the lightweight-charts instance.

### 5. Testing & Devops
* **Async Test Suite Execution**: Run test suites with `-p no:anyio` to let `pytest-asyncio` handle session-scoped event loops cleanly without hangs.
* **Infinite Event Streams Mocking**: Raise `asyncio.CancelledError` inside async generator loops to terminate tests instead of using long sleeps.
* **Production Deployment Flow**: Always run deployment operations using `sudo /opt/trading-journal/deploy.sh` since production paths are owned by the `root` user. Commit and push from developer workspace `/home/jackc/projects/homma-research` first.

---

## 🔱 Branch: `session` (Active Intent & Scope)

### Current Session: Live Screener Latency & Momentum Percentage Fixes
* **Goal**: Fix screener indexing latency (e.g. ABAT taking 15m to appear) and resolve incorrect/stale values in the 2-minute momentum column.
* **Forked context**: Inspected TradingView candidate scanner limitations and the old index-based `mom_2m` calculations.
* **Merged decisions**:
  - Combined TradingView, Schwab Movers (NYSE, NASDAQ, and EQUITY_ALL), and watchlisted symbols into the hybrid candidate pool in [schwab_client.py](file:///home/jackc/projects/homma-research/backend/services/schwab_client.py) to eliminate indexing delays.
  - Refactored `mom_2m` calculation in [live_screener.py](file:///home/jackc/projects/homma-research/backend/services/live_screener.py) to use a robust timestamp-based lookback instead of raw indices.
  - Added real-time updates for `mom_2m` inside the 30-second in-memory cache of `get_minute_metrics` whenever a new quote ticks.
* **Pruned context**: None.

---

## 🗑️ Rot & Pruning Log (Technical Debt Registry)
*Items listed here are marked for deletion or review next session if their underlying assumptions hold true.*
- *None currently listed.*
