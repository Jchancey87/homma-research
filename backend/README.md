# Trading Journal Backend 🐍

The backend is a Flask-based REST API that handles data ingestion, AI analysis, and serving market data to the frontend.

## 🏗️ Architecture

The backend is organized into several key layers:

### Routes (Blueprints)
- `routes/gainers.py` — Top gainers CRUD, filtering, heatmap data, CSV export.
- `routes/charts.py` — Chart capture uploads, OHLCV data for `lightweight-charts`.
- `routes/analysis.py` — All LLM job endpoints (deep research, risk, catalyst, context, continuation, sentiment).

### Services
Business logic is fully decoupled from routes for testability and reuse:

| Service | Purpose |
|---|---|
| `fmp_service.py` | Financial Modeling Prep integration — fundamental metrics, cash runway, earnings, analyst targets, institutional ownership |
| `sec_service.py` | SEC EDGAR integration — CIK lookup, filing fetches (Submissions API), EFTS full-text search, XBRL shares history |
| `risk_service.py` | Risk Detection data pipeline — reverse splits, short interest, insider activity, S-3/424B filings, toxic financing search |
| `catalyst_service.py` | Catalyst Analysis data pipeline — Polygon news, SEC 8-K items, FMP earnings, analyst upgrades, freshness scoring |
| `context_service.py` | Deep Context data pipeline — SMA/EMA levels, FMP RS vs SPY, options flow, journal history |
| `chart_service_research.py` | Intraday chart generation (Polygon + mplfinance) for the main research report |
| `gainer_service.py` | Gainer data queries and filtering |
| `archetype_service.py` | Pattern categorization stats |
| `heatmap_service.py` | Float × RVOL heatmap data |

### LLM Layer
- `llm/llm_client.py` — All Groq (text) prompt templates and functions:
  - `get_risk_analysis()` — Structured risk report with severity scoring per factor.
  - `get_catalyst_analysis()` — Tier 1/2/3 catalyst quality assessment.
  - `get_deep_context()` — Setup Score (1–10) with playbook table.
  - `get_ticker_deep_research()` — Full fundamental + technical analyst report.
  - `get_continuation_analysis()` — Nightly continuation watch list.
  - `classify_news_fresh()` — Single-shot FRESH/STALE headline classifier.
- `llm/vision_client.py` — Gemini (vision) for chart image annotation.

### Jobs (Automation)
- `jobs/ingest_gainers.py` — Pulls top daily gainers from Polygon at market close.
- `jobs/daily_analysis_report.py` — Generates and emails the nightly AI report.

### Database
- `database.py` — PostgreSQL connection pool using `psycopg2`.
- `models/schema.sql` — Idempotent schema for `daily_gainers`, `chart_captures`, `llm_jobs`, and `pipe_filings`.

---

## 🚀 Getting Started

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Environment — your `backend/.env` must contain:

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL DSN: `postgresql://user:pass@host:5432/db` |
| `POLYGON_API_KEY` | ✅ | Market data (OHLCV, news, reference) |
| `FMP_API_KEY` | ✅ | Financial Modeling Prep key |
| `LLM_API_KEY` | ✅ | Groq API key |
| `LLM_MODEL` | Optional | Default: `llama-3.3-70b-versatile` |
| `GEMINI_API_KEY` | Optional | Vision chart annotation |
| `SEC_USER_AGENT` | ✅ | `Your Name your@email.com` — SEC EDGAR header requirement (free) |
| `SMTP_*` | Optional | Email credentials for daily reports |

### Running the Server

```bash
python app.py
```
The server defaults to `http://127.0.0.1:5000`.

---

## 📡 API Endpoints

### Research & Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/research` | Start full deep-dive research job (main report + vision chart) |
| POST | `/api/research/risk` | Start Risk Detection job (SEC filings, short interest, insider activity) |
| POST | `/api/research/catalyst` | Start Catalyst Analysis job (news, 8-K items, earnings, freshness) |
| POST | `/api/research/context` | Start Deep Context job (SMA, RS vs SPY, options, journal history) |
| GET | `/api/research/chart-data` | OHLCV + indicators for `lightweight-charts` frontend |
| GET | `/api/jobs/<job_id>` | Poll job status (`pending` → `running` → `done`/`error`) |
| GET | `/api/jobs` | List recent LLM jobs |

> All `POST /api/research/*` routes accept `{ ticker, date? }` and immediately return `{ job_id }`.
> The frontend polls `GET /api/jobs/<job_id>` every 2.5s until `status === 'done'`.

### Gainers & History

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/gainers` | Filter gainers by date, gap, float, RVOL, sector |
| GET | `/api/gainers/summary` | Dashboard briefing: latest ingest stats + top 9 gainers |
| GET | `/api/gainers/ticker-history` | Aggregated per-ticker history (appearances, avg gap, etc.) |
| GET | `/api/gainers/ticker/<ticker>` | Individual appearance log for a specific ticker |
| GET | `/api/gainers/heatmap` | Float × RVOL heatmap data (period-aware) |
| GET | `/api/gainers/pipe-scan` | Batch-scan a date for PIPE/private placement activity |
| GET | `/api/gainers/sectors` | Unique sector list |
| GET | `/api/gainers/export` | CSV export (honours active filters) |
### Watchlist & Observations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/watchlist` | List all tickers on watchlist |
| POST | `/api/watchlist` | Add/update ticker on watchlist |
| DELETE | `/api/watchlist/<ticker>` | Remove ticker from watchlist |
| GET | `/api/observations` | List latest historical observations |
| POST | `/api/observations` | Add new note/observation for a ticker |

### Charts & Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/charts` | List / upload chart captures |
| GET | `/api/health` | System status, DB reachable, LLM model info |
| GET | `/api/archetypes` | Archetype performance stats |

---

## ⏲️ Background Jobs (Cron)

```bash
# Gainer ingestion — 4:15 PM EST weekdays
15 16 * * 1-5 /path/to/venv/bin/python /path/to/backend/jobs/ingest_gainers.py

# Daily email report — 6:00 PM EST weekdays
00 18 * * 1-5 /path/to/venv/bin/python /path/to/backend/jobs/daily_analysis_report.py
```

---

## 🧪 Testing

Test scripts in the backend root directory:
- `test_full_pipeline.py` — Full ingestion → analysis flow.
- `test_yf_fallback.py` / `test_yf_fallback2.py` — yfinance fallback validation.
- `test_chart.py` / `test_chart2.py` — Chart generation validation.
- `test_polygon_date.py` — Polygon date boundary tests.
