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
* **Timestamp-Based Lookback (Wall-Clock Anchor)**: Compute `mom_2m` in [live_screener.py](file:///home/jackc/projects/homma-research/backend/services/live_screener.py) using `time.time()` (wall-clock now in ms) minus 120,000 ms as the reference, NOT `candles[-1].get('t')`. The last candle timestamp may itself be stale on slow/gapped tickers, skewing the window backward.
* **Fallback Candle Capping**: When no candle ≥2 min old exists, fall back to the **earliest candle within the last 5 minutes**. Never fall back to `candles[0]` (4 AM pre-market open) which made `mom_2m` reflect the entire-day move instead of 2-minute momentum.
* **Dynamic Cache Recalculation**: Cache `price_2min_ago` in memory and dynamically update `mom_2m` within the 30-second cache window whenever a new `last_price` quote arrives, keeping the UI value responsive.
* **Schwab as Primary Discovery Source**: In [schwab_client.py](file:///home/jackc/projects/homma-research/backend/services/schwab_client.py) `get_gainers_snapshot`, Schwab Movers (NASDAQ, NYSE, EQUITY_ALL) is seeded FIRST as the primary real-time source. TradingView runs second as enrichment only (adds float/sector/market_cap). TV never overwrites Schwab change/price/volume unless it has a strictly higher absolute % change. This eliminates the ~15-min TradingView indexing lag.

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

### Current Session: Screener Candidate Priority & mom_2m Anchor Fix (Round 2)
* **Goal**: Fix `mom_2m` using wrong anchor (last candle ts vs wall-clock now), fix candle[0] fallback bug, and invert Schwab/TradingView discovery priority.
* **Bugs identified from `live_gainers.html`**:
  - GMHS: +77.9% gap but -3.45% mom → mom was comparing vs very old candle (4 AM fallback)
  - Discovery latency: TradingView's 15-min indexing window was the primary bottleneck
* **Fixes applied**:
  - `mom_2m` now anchored to wall-clock `time.time()` in ms, not `candles[-1].get('t')`
  - Fallback capped to last 5-minute window instead of `candles[0]`
  - Schwab Movers seeded first; TradingView runs as enrichment pass only

---

## 🗑️ Rot & Pruning Log (Technical Debt Registry)
*Items listed here are marked for deletion or review next session if their underlying assumptions hold true.*
- *None currently listed.*
