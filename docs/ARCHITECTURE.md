# System Architecture 🏗️

The Trading Pattern Journal is a self-hosted, distributed local application consisting of a Python/Flask backend and a Next.js frontend with a multi-source data pipeline and a multi-module AI research engine.

## 🧱 Component Overview

### 1. Data Ingestion Layer

| Source | Used For | Auth |
|---|---|---|
| **FMP (Financial Modeling Prep)** | Fundamentals, earnings calendar, analyst estimates, enterprise value | API Key |
| **Massive.com** (fka Polygon.io) | Real-time OHLCV, daily aggregates, gainers snapshot, news articles — via official `massive` Python SDK (`services/polygon_client.py`) | API Key |
| **SEC EDGAR Submissions API** | Company filings (S-3, 8-K, 424B) | User-Agent header only |
| **SEC EDGAR EFTS** | Full-text search for toxic financing keywords | User-Agent header only |
| **SEC EDGAR XBRL** | Quarterly shares outstanding (dilution trend) | User-Agent header only |
| **yfinance** | Fallback fundamentals, insider/institutional data | None |
| **finviz** | Short interest confirmation, screener data | None |

### 2. Backend Service Layer (FastAPI + Celery)

- **Modular Routers**: The API is segmented into `gainers`, `market`, `watchlist`, `charts`, `analysis`, and `alerts` routers registered at `/api`.
- **Market Intelligence Router**: A specialized high-performance route providing live index status (SPY/QQQ/IWM) and high-impact economic events (FMP Economic Calendar) with aggressive caching (15min/6h) to preserve API quotas.
- **Service-Oriented Design**: All data gathering lives in `services/`, completely decoupled from routes. Market data calls are centralised through `services/polygon_client.py` (official Massive SDK adapter) — no raw HTTP calls to Massive/Polygon endpoints outside this module.
- **Async Job Pattern**: All LLM-heavy operations (`/api/research/*`) immediately return a `job_id` and run via Celery workers. The frontend polls `GET /api/jobs/<job_id>` until completion. Jobs are persisted to PostgreSQL (`llm_jobs` table).
- **`services/news_aggregator.py`**: Pluggable news aggregation layer. `NewsSource` abstract base class defines the interface; `YFinanceNewsSource` is the live implementation; `BenzingaNewsSource` is a stub for a future in-house aggregator. `NewsAggregator` fan-out orchestrator merges results from all sources. Wire new sources in `get_default_aggregator()`.
- **`services/pump_classifier.py`**: No-News Pump detector. Phase 1 (`stamp_catalyst_tags`) runs on every screener refresh with zero I/O. Phase 2 (`start_news_enrichment_loop`) runs a daemon thread every 3 minutes during market hours, calling `NewsAggregator` to verify and upgrade tags. Writes to `pump_classifications` table.

### 3. AI Analysis Engine

The AI layer has two clients and six prompt functions:

**Text (Groq — Llama 3.3 70B):**
- `get_risk_analysis()` — Forensic risk report with per-factor severity scores.
- `get_catalyst_analysis()` — Tier 1/2/3 catalyst quality assessment.
- `get_deep_context()` — Setup Score (1–10) with technical + structural playbook.
- `get_ticker_deep_research()` — Full fundamental + technical analyst report.
- `get_continuation_analysis()` — Nightly continuation watch list.
- `classify_news_fresh()` — Single-shot FRESH/STALE classifier.

**Vision (Gemini 1.5 Pro):**
- `analyze_charts_multi_tf()` — Analyzes mplfinance session charts (EMA ribbon, RVOL, ADX, ATR panels) and returns a structured technical verdict.

### 4. Frontend Interface (Next.js 14)

- **App Router** with server-side structure and client components where needed.
- **Interactive Charting** with `lightweight-charts` (EMA 8/13/21/34/55 ribbon, RVOL, ADX +DI/-DI, ATR).
- **Deep Research Tabs** — 4 independent analysis modules that fire in parallel.
- **`FeaturePanel`** — Reusable React component for each research module with its own polling state, loading/error/report rendering, and Re-run button.

---

## 🔄 Data Flow: A Ticker's Journey

### Daily Automation
```
Market Close (4pm ET)
  → ingest_gainers.py: Massive.com top gainers snapshot (ET-aware)
      gap% = (day_open - prev_close) / prev_close   ← authoritative grouped daily bar
      → pump_classifier.classify_catalyst()          ← stamps Confirmed Catalyst / Technical / No News / Speculative
      → PostgreSQL daily_gainers table (incl. catalyst column)
      → PostgreSQL pump_classifications table (historical tag log)
  → daily_analysis_report.py: Top 3 gainers → Groq analysis → email

Morning Briefing (4am – 9:30am ET)
  → /api/market/breadth: Live SPY/QQQ/IWM performance + Risk Bias
  → /api/gainers/repeat-runners: Cross-reference live gainers vs DB history
  → /api/watchlist/prices: Batch Polygon snapshots for user watchlist
  → /api/market/calendar: FMP high-impact event feed

Live Screener (every 60 seconds during market hours)
  → live_screener.refresh_cache(): Polygon snapshot → Schwab enrichment
      → stamp_catalyst_tags()      ← Phase 1: instant in-memory classification
      → [background thread, every 3 min]
          → NewsAggregator.has_news() ← Phase 2: yfinance verification
          → upgrades tag to 'Confirmed Catalyst' if news found
          → pump_classifications upsert
```

### On-Demand Research (parallel)
```
User enters ticker → clicks ANALYZE
  │
  ├── [Thread 1] /api/research
  │     FMP fundamentals + Massive.com intraday → mplfinance chart
  │     → Gemini vision analysis → Groq DEEP_RESEARCH_SYSTEM → Full Report
  │
  ├── [Thread 2] /api/research/risk
  │     FMP (splits, short, insider, cash) + SEC EDGAR (S-3, 424B, EFTS)
  │     → Groq RISK_DETECTION_SYSTEM → Risk Report
  │
  ├── [Thread 3] /api/research/catalyst
  │     Massive.com news + SEC 8-K filings + FMP earnings calendar + freshness scoring
  │     → Groq CATALYST_ANALYSIS_SYSTEM → Catalyst Report (Tier 1/2/3)
  │
  └── [Thread 4] /api/research/context
        Massive.com daily OHLCV (SMA) + FMP RS vs SPY + options data
        + PostgreSQL daily_gainers history for this ticker
        → Groq DEEP_CONTEXT_SYSTEM → Setup Score + Playbook
```

Each thread writes to `llm_jobs` in PostgreSQL. Frontend polls all 4 `job_id`s in parallel every 2.5s.

---

## 🗄️ Database Schema

**`daily_gainers`**: One row per ticker per date. Core market metrics (gap%, float, RVOL, sector, headlines, catalyst tag).

**`pump_classifications`**: Historical log of No-News Pump catalyst tags per ticker per date. Columns: `ticker`, `date`, `catalyst_tag` (`Confirmed Catalyst` | `Technical / No News` | `Speculative`), `gap_pct`, `rvol`, `float_shares`, `classified_at`, `news_source` (`lightweight_check` | `yfinance_verify` | `ingest_pipeline`). Unique constraint on `(ticker, date)` with upsert to track intraday upgrades.

**`chart_captures`**: Trade screenshots with tags, cleanliness score, Gemini annotation, and optional re-uploaded annotated image.

**`llm_jobs`**: All LLM analysis jobs — `type` distinguishes `research`, `risk_detection`, `catalyst_analysis`, `deep_context`, `continuation`, `sentiment`.

---

## 🛠️ Infrastructure

- **Process Management**: PM2 (`ecosystem.config.js` in project root) for automatic restart and log management.
- **Reverse Proxy**: Nginx Proxy Manager for secure LAN access (`journal.local`).
- **SEC EDGAR**: Free, no registration. Set `SEC_USER_AGENT=Your Name your@email.com` in `.env`.
