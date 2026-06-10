# Active Agent Memory & Decisions (AGENT_MEMORY.md) 🧠

> ⚠️ STRICT CONSTRAINT: This file MUST remain under 500 tokens. Prune, modify, or delete sections as soon as they become stale or resolved by clean code patterns. Memory is training data for decisions, not archival storage.

## 🌿 Branch: main (Persistent Core Decisions)

### 1. Schwab API Integration & Reliability
* **Thread-Safety:** `get_http_client()` uses `threading.local()`. Never share the HTTP client globally across threads to avoid socket deadlocks.
* **API Parsing:** Convert Schwab's `{'instruments': [...]}` list into a dictionary keyed by symbol before doing lookups.
* **Scale Multipliers:** `sharesOutstanding` and `marketCap` are absolute integers. Do not apply redundant 1,000,000 multipliers.
* **Unified Candidate Pulling:** `get_gainers_snapshot` merges Schwab Movers (NASDAQ, NYSE, EQUITY_ALL) first as primary real-time source, then TradingView (enrichment only), then user watchlist. Trim to top 150. Watchlist always prioritizes first and bypasses filters. TV data never overwrites Schwab unless its absolute % change is strictly higher.
* **Movers API Mapping:** Multiply `netPercentChange` (fractional, e.g., 0.6246) by 100 to get percentage.

### 2. Alert System & Hysteresis State Machine
* **Watchlist Constraint:** Stream alerts must only evaluate symbols in `self.watchlist_symbols`.
* **VWAP Hysteresis:** Evaluate crossovers using a state machine ('above'/'below') with a ±2.0 buffer.
* **Adaptive Cooldowns:** Use SQL `alerts.should_fire_alert`. Enforces price-bucket adaptive percentages (2%-8%) and 2-min lockouts.
* **Body-Close Confirmation:** HOD breakouts require a completed 1-minute candle close confirmation.
* **Halt Suppression:** Suppress momentum triggers for 2 minutes following a volatility halt resume.

### 3. Live Screener & Momentum Calculations
* **Architecture:** `live_screener.py` is a flat 5-step pipeline. No nested wrappers, no layered state.
* **mom_2m Calculation:** `best = min(candles, key=lambda c: abs((c.get('t') or 0) - target_ts))` where `target_ts = now_ms - 120_000`. Use `best['c']` as base price. Single line, no fallback loops needed.
* **mom_2m Staleness Guard (MAX_MOM_CANDLE_AGE_S=300):** Rejects any "best" candle that is >5 mins from the 2-min-ago target, returning `None` instead of stale percentages (handles session start transitions).
* **Session-Transition Cache Flush:** The background refresh loop tracks `_last_session` and clears `_minute_cache` and `_daily_cache` on session transitions to prevent data leakage.
* **30s Minute Cache:** `_compute_minute_metrics` caches for 30s. Within that window it updates `mom_2m`, `atr_hod`, `atr_sprd`, `atr_vwap` inline using the cached `price_2min_ago` and `atr_14` — no re-fetch needed.
* **Filters:** MIN_GAP_PCT=5.0, MIN_PRICE=$0.50, MAX_PRICE=$100.

### 4. Frontend & UI Performance
* **Toggle-on-Click:** Large lists expand details only on explicit click. No hover/enter state handlers.
* **Audio:** Synthesize chimes dynamically via Web Audio API (`playPlinkChime`). No raw audio assets.
* **Chart Centering:** Split chart initializations and decorations into separate hooks in `page.tsx` to update indicators without recreating the chart instance.

### 5. Testing & DevOps
* **Async Execution:** Run test suites with `-p no:anyio` for clean pytest-asyncio session loops.
* **Mocking:** Raise `asyncio.CancelledError` inside async generator loops to terminate tests.
* **Deployment:** Run operations using `sudo /opt/trading-journal/deploy.sh`. Commit/push from `/home/jackc/projects/homma-research` first.

## 🔱 Branch: session (Active Intent & Scope)
* **Current Session:** Live Screener Full Refactor.
* **Completed:** Flat pipeline rewrite of `live_screener.py` (888 lines). Fixed `alerts.py` `get_alerts_performance` passing `days: int` directly to asyncpg by converting to `str(days)`.

## 🗑️ Rot & Pruning Log
* None.

---

## 🛑 AGENT RESTRAINT: TOKEN BUDGET ENFORCEMENT
Before saving updates to this file, you MUST calculate the token count. If changes push this file over 500 tokens, you must aggressively compress prose, combine bullet points, or delete older, fully-implemented operational context from the "main" branch.
