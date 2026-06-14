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
* **Goal:** Execute the 3 highest-priority RFCs from the architectural audit (RFC-001, RFC-002, RFC-003).
* **Status:** ALL COMPLETE. 150 tests pass; 0 regressions.
* **RFC-001** (extract analytics into deep services):
  - New services: [chart_data_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_data_service.py), [alerts_analytics.py](file:///home/jackc/projects/homma-research/backend/services/alerts_analytics.py), [continuation_analytics.py](file:///home/jackc/projects/homma-research/backend/services/continuation_analytics.py).
  - Routers slimmed: analysis.py 528→307, alerts.py 370→142, continuation.py 283→147 (-585 lines total).
  - +58 new unit tests (test_chart_data_service, test_alerts_analytics, test_continuation_analytics).
  - AGENTS.md §4 "Router Layer Rules" added.
* **RFC-002** (consolidate Schwab access):
  - Deleted [polygon_client.py](file:///home/jackc/projects/homma-research/backend/services/polygon_client.py) + [polygon_service.py](file:///home/jackc/projects/homma-research/backend/services/polygon_service.py) shims (-30 lines).
  - [schwab_client.py](file:///home/jackc/projects/homma-research/backend/services/schwab_client.py) is now the single canonical import path; re-exports all 8 upstream helpers + 9 legacy adapters.
  - 10 callers migrated (4 routers, 3 jobs, 1 service, 2 intra-service).
* **RFC-003** (unify config):
  - Merged [backend/config.py](file:///home/jackc/projects/homma-research/backend/config.py) (legacy `Config` UPPER_CASE) + [fastapi_app/config.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/config.py) (`Settings` lowercase) into one file.
  - Eliminated silent DATABASE_URL divergence (different password + host).
  - [fastapi_app/config.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/config.py) now a 2-line re-export. All 25 importer sites work unchanged.
* **Next:** Audit re-run + devlog entry; consider RFC items #4-#5 (db module adoption, live-quotes service).

## 🗑️ Rot & Pruning Log
* Pruned debug ticker research goal. Completed.
* Applied Caveman Style rules.

