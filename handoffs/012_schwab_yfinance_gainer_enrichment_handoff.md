# Schwab & YFinance Daily Gainer Enrichment & OpenRouter Migration — Handoff

## Overview
This document outlines the implementation details for the **EOD Daily Gainer Enriched Metrics** pipeline and the migration of the primary LLM client from **Groq** to **OpenRouter**. It includes details on bug fixes related to timezone day-ahead shifts, database transaction failures, schema modifications, and steps for future validation.

---

## 🚀 Key Implementations

### 1. Daily Gainer Quantitative Enrichment
The post-close gainer ingestion pipeline now queries the **Schwab market data API** and **yfinance** to calculate and store institutional-grade metrics for a 1-minute momentum scalper:
* **Premarket Stats**: Calculates premarket range (`premarket_high`, `premarket_low`) and total premarket volume (`premarket_volume`) on 1-min charts prior to the 9:30 AM ET market open.
* **Intraday VWAP Profile**: Computes regular session volume-weighted average price (VWAP) and the percentage of time the price closed above VWAP (`pct_above_vwap`).
* **Multi-Timeframe Technicals**: Calculates 14-day Average True Range (`atr_14`) along with the 20-day and 50-day Simple Moving Averages (`sma_20`, `sma_50`).
* **Cash Runway & Dilution Risk**: Queries yfinance balance sheet and cash flow statements to fetch total cash, net income, and operating cash flow (OCF). Computes cash runway in months (`runway_months = (cash / absolute_burn) * 3`) and flags financing/dilution risk (`dilution_risk = Low | Moderate | High`) based on multi-quarter share counts and runway limits.

### 2. Timezone Date Calculation Bug Fixes
* **The Issue**: The server runs in the UTC timezone. When ingestion or reporting ran after 8:00 PM UTC (4:00 PM ET), `datetime.date.today()` evaluated to the next calendar date (UTC day-ahead). Consequently, Thursday's session data was logged as Friday's, presenting stale data.
* **The Fix**: Standardized target date calculations across the scheduler and daily report to explicitly target the `US/Eastern` timezone.
  * In [scheduler.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/scheduler.py) and [daily_analysis_report.py](file:///home/jackc/projects/homma-research/backend/jobs/daily_analysis_report.py), the default date is now calculated as:
    ```python
    import pytz
    from datetime import datetime
    eastern = pytz.timezone('US/Eastern')
    target_date = datetime.now(eastern).strftime('%Y-%m-%d')
    ```

### 3. Database Transaction Abort Bug Fix
* **The Issue**: PostgreSQL aborts the entire transaction block if any query raises an exception (e.g., unique key constraint violations on duplicate gainers). The loop in `write_gainers` caught the exception but did not rollback, causing all subsequent insertions in the transaction block to fail.
* **The Fix**: Replaced the standard `INSERT` statement in [ingest_gainers.py](file:///home/jackc/projects/homma-research/backend/jobs/ingest_gainers.py) with a PostgreSQL native `UPSERT` statement (`ON CONFLICT (date, ticker) DO UPDATE SET ...`). This prevents unique key exceptions from being raised and successfully updates existing gainers with EOD post-close stats.

### 4. Primary LLM Provider Migration (Groq → OpenRouter)
* Updated primary LLM configurations in [.env](file:///home/jackc/projects/homma-research/backend/.env) (documented in [.env.example](file:///home/jackc/projects/homma-research/.env.example)) to point to the OpenRouter endpoint using the shared API key and the `meta-llama/llama-3.3-70b-instruct` model.
* Updated [llm_client.py](file:///home/jackc/projects/homma-research/backend/llm/llm_client.py) to pass the required headers (`HTTP-Referer` and `X-Title`) during client instantiation.

---

## 🗄️ Database Schema Modifications
The following columns were added to the `daily_gainers` table via manual database migration and updated in the core [schema.sql](file:///home/jackc/projects/homma-research/backend/models/schema.sql) file:

```sql
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS premarket_high      DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS premarket_low       DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS premarket_volume    DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS pct_above_vwap      DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS atr_14              DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS sma_20              DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS sma_50              DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS cash                DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS net_income          DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS operating_cash_flow  DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS runway_months       DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS dilution_risk       TEXT;
```

---

## 🛠️ Modified Files
* **Schema**: [schema.sql](file:///home/jackc/projects/homma-research/backend/models/schema.sql)
* **Ingestion Logic**: [ingest_gainers.py](file:///home/jackc/projects/homma-research/backend/jobs/ingest_gainers.py)
* **Daily Report Logic**: [daily_analysis_report.py](file:///home/jackc/projects/homma-research/backend/jobs/daily_analysis_report.py)
* **LLM Client Settings**: [llm_client.py](file:///home/jackc/projects/homma-research/backend/llm/llm_client.py)
* **Environment Configuration**: [.env](file:///home/jackc/projects/homma-research/backend/.env) (and [.env.example](file:///home/jackc/projects/homma-research/.env.example))

---

## 🔄 Deployment & Verification

### Deploy Changes
Run the deployment script from your `/opt/trading-journal` production root:
```bash
cd /opt/trading-journal
sudo ./deploy.sh
```

### Validate Ingestion and Data Storage
Run the ingestion script manually for a specific date to check for console output and warnings:
```bash
/opt/trading-journal/backend/venv/bin/python3 /opt/trading-journal/backend/jobs/ingest_gainers.py --date 2026-05-29
```

Query the database directly to confirm the new values are being stored:
```sql
SELECT ticker, date, premarket_high, premarket_volume, runway_months, dilution_risk 
FROM daily_gainers 
WHERE date = '2026-05-29' AND premarket_high IS NOT NULL;
```
