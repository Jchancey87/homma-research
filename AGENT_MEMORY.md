# Active Agent Memory & Decisions (AGENT_MEMORY.md) 🧠

> ⚠️ STRICT CONSTRAINT: Keep under 500 tokens. Prune/delete stale info.

## 🌿 Branch: master (Persistent Core Decisions)
* **Sector Relative Strength (OneOption strategy concept):** Replaced `MarketRegimeCard` with `SectorStrengthCard` measuring 11 GICS sector SPDR ETFs vs SPY intraday. Powered by `services/sector_strength_service.py` (`build_sector_strength`) and `/api/market/sector-strength`.
* **MTF S/R Scanner Engine (ADR 0007):** Stateless S/R calculation and 100-point rebalanced confluence matrix in `backend/services/mtf_sr_service.py`. Generates Tier 1 Daily, Tier 2 5-min, and Coincident levels. Streamed via Schwab Streamer loop to Redis & `/api/market/mtf-scanner`. Rendered in `MTFScannerWidget.tsx`.
* **Alert System DISABLED (2026-08-06):** `ALERTS_DISABLED = True` in `stream_client.py` (skips Redis publish + Telegram) and `tasks/alerts.py` (no-ops both Celery tasks). DB writes still run. Flip both flags to `False` to re-enable. Migration needed before TS import: `sql/ts_alerts_source_migration.sql`.
* **TradeStation Import:** `POST /api/ts-alerts/import/csv` and `/json` in `fastapi_app/routers/ts_alerts.py`. Populates `screener_alerts` with `source='tradestation'`. Charts TBD.

## 👤 Session
* **Status:** Complete.
* **MTF S/R Momentum Scanner Upgrade:**
  - Enhanced `mtf_sr_service.py` to calculate enriched metrics (RVOL, float category, % gain, distance to S/R, volume, VWAP, sparklines, breakout status).
  - Added Warrior momentum filtering ($1–$20 price, RVOL ≥ 5.0x, float < 20M) in scanner engine, API endpoint (`/api/market/mtf-scanner`), and streaming loop.
  - Overhauled `MTFScannerWidget.tsx` with high-density pro UI: presets (Warrior Low-Float, High Conviction, Confluence, Nano Float), filter bar (price/rvol/float/score), table/grid views, S/R proximity meters, score breakdowns, signal badges, and direct chart/watchlist integration.

### 1. Codebase Architecture Refactoring (Chunks 1–5 Completed)
- **Chunk 1 (Alert Engine)**: Decoupled alert detection into pure, stateless `backend/services/alert_detection_service.py` (ADR-0001). `stream_client.py` handles downstream DB/Redis/Telegram side-effects.
- **Chunk 2 (LLM Prompt & Transport)**: Extracted `LLMTransport` (`backend/llm/transport.py`), pure prompt builders (`backend/llm/prompts.py`), and domain analyzers (`backend/llm/analyzers/`). `llm_client.py` is a thin facade maintaining 100% test compatibility (ADR-0002).
- **Chunk 3 (Screener Pipeline & Cache)**: Extracted pure math to `backend/services/screener_metrics.py`, thread-safe cache to `backend/services/screener_cache.py`, and API candidate sourcing to `backend/services/screener_source.py`. `live_screener.py` is a thin ~150-line orchestrator (ADR-0003).
- **Chunk 4 (Frontend API Client)**: Modularized `frontend/lib/api.ts` into `client.ts`, `types.ts`, `gainers.ts`, `alerts.ts`, `market.ts`, and `analysis.ts` under `frontend/lib/api/`. `api.ts` serves as a transparent barrel export facade (ADR-0004).
- **Chunk 5 (Fat Routers & RFC-001)**: Extracted `MarketService` (`market_service.py`), `GainersService` (`gainers_service.py`), and `AnalysisService` (`analysis_service.py`) out of routers to enforce RFC-001 thin router rules (ADR-0005).

### 2. Schwab API & Data
* **Thread-Safety:** `get_http_client()` uses `threading.local()`. Never share client across threads.
* **Unified Candidate Pulling:** Primary source is Schwab Movers, fallback/enrich from TV, plus watchlists. Limit to 150. TV never overwrites Schwab unless its % change is strictly higher.
* **Live Quotes (RFC-004 QW-1):** All router-side batch quote fetching goes through `services.live_quotes_service.get_live_quotes(tickers, *, polygon_api_key=None)`. Returns `dict[ticker, NormalizedQuote]`.

### 3. Alerts & Hysteresis State Machine
* **Scope:** Evaluate symbols in `self.watchlist_symbols` only.
* **Triggers:** VWAP crossover uses hysteresis state ('above'/'below') ±2.0 buffer. NEAR_HOD_RADAR breakout triggers on live price tick exceeding previous session high. Cooldowns use `alerts.should_fire_alert`.
* **Tier Naming Convention:** `priority_tier` = Alert Tier (confluence score signal strength). `catalyst_tier` = Catalyst Tier (LLM news quality rating). Never mix these concepts.

### 4. Validation Helpers (RFC-004 QW-4)
* **Ticker normalisation:** `from validation import normalize_ticker` — uppercase + strip.
* **US/Eastern tz:** `from validation import EASTERN_TZ` — `pytz.timezone("America/New_York")` singleton. Replaces raw `pytz.timezone(...)` constructors everywhere.

### 5. Testing & DevOps
* **Venv Testing:** Execute backend tests using `/opt/trading-journal/backend/venv/bin/pytest`.
* **Async tests:** Run with `-p no:anyio` for clean asyncio loops.
* **Test surface:** 277 passing, 0 regressions. Next.js build: `npm run build` green (0 errors).

