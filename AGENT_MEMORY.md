# Active Agent Memory & Decisions (AGENT_MEMORY.md) 🧠

> ⚠️ STRICT CONSTRAINT: Keep under 500 tokens. Prune/delete stale info.

## 🌿 Branch: main (Persistent Core Decisions)

### 1. Schwab API & Data
* **Thread-Safety:** `get_http_client()` uses `threading.local()`. Never share client across threads.
* **Unified Candidate Pulling:** Primary source is Schwab Movers, fallback/enrich from TV, plus watchlists. Limit to 150. TV never overwrites Schwab unless its % change is strictly higher.
* **API Details:** Key Schwab `instruments` by symbol before lookups. `sharesOutstanding` and `marketCap` are absolute ints. Multiply `netPercentChange` by 100.

### 2. Alerts & Hysteresis State Machine
* **Scope:** Evaluate symbols in `self.watchlist_symbols` only.
* **Triggers:** VWAP crossover uses hysteresis state ('above'/'below') ±2.0 buffer. HOD breakouts require 1-min body-close. Suppress triggers for 2 mins post-halt. Cooldowns use `alerts.should_fire_alert`.

### 3. Live Screener & Momentum
* **Pipeline:** Flat 5-step flow in `live_screener.py`.
* **mom_2m:** Calculated relative to target 2m ago. If closest candle is >5m old, return `None`.
* **Caching & Sparklines:** 30s cache updates metrics inline. Daily cache holds 5d metrics. Flush caches on market session transitions. `sparkline_1h` caches last 60m of minute closes.
* **Filters:** MIN_GAP_PCT=5.0, MIN_PRICE=$0.50, MAX_PRICE=$100.

### 4. Frontend & UI
* **Interaction:** Toggle row expansion on click. No hover handlers.
* **Audio/Charts:** Dynamic chimes via Web Audio API. Split chart hooks (init vs decorators) in `page.tsx`.

### 5. Testing & DevOps
* **Venv Testing:** Execute backend tests using `/opt/trading-journal/backend/venv/bin/pytest`.
* **Async tests:** Run with `-p no:anyio` for clean asyncio loops.
* **Deploy:** Run `sudo /opt/trading-journal/deploy.sh` (push from `/home/jackc/projects/homma-research` first).

## 🔱 Branch: session (Active Intent & Scope)
* **Goal:** Diagnose high CPU usage.
* **Findings:** Expired Schwab OAuth token causes infinite PM2 restart loop on `schwab-streamer` and spamming `fastapi-backend` error logs.
* **Remediation:** Recommend manual OAuth token re-authorization using `schwab_auth_setup.py`.

## 🗑️ Rot & Pruning Log
* Pruned debug ticker research goal. Completed.
* Applied Caveman Style rules.

