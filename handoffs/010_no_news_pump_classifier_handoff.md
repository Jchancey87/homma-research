# No-News Pump Classifier & News Aggregator Handoff

**Date**: 2026-05-26  
**Scope**: Full-stack — backend services, DB migration, EOD ingest, live screener, frontend UI  
**Status**: ✅ Complete & deployed

---

## 1. What Was Built

A two-phase catalyst classification system that automatically tags every live gainer with one of three tiers and surfaces the result in the UI — so you can instantly tell whether a move is fundamental or pure tape-speed speculation.

### Catalyst Tier Taxonomy

| Tag | Trigger Condition | UI |
|---|---|---|
| `Confirmed Catalyst` | `news_headline` is populated | Existing italic headline text in drawer |
| `Technical / No News` | No news + `gap_pct ≥ 30%` + `rvol_15m ≥ 2x` | Orange ⚠️ **NNP** pill in table row + orange badge in drawer |
| `Speculative` | No news + low or unknown RVOL | Gray **? SPEC** pill in table row + gray badge in drawer |

---

## 2. New Files

### [`backend/services/news_aggregator.py`](file:///home/jackc/projects/homma-research/backend/services/news_aggregator.py)
Pluggable news source interface built on Python ABCs.

```
NewsSource (ABC)
  └── get_news(ticker, hours_back) -> list[dict]

YFinanceNewsSource(NewsSource)     ← live, no API key required
BenzingaNewsSource(NewsSource)     ← stub, raises NotImplementedError

NewsAggregator
  └── fan-out orchestrator, de-duplicates by title prefix
  └── has_news(ticker, hours_back) -> bool   ← short-circuits on first hit

get_default_aggregator() -> NewsAggregator  ← update here to add future sources
```

**To plug in a future in-house aggregator:**
1. Create a class that subclasses `NewsSource`
2. Implement `get_news(ticker, hours_back) -> list[dict]`
3. Add it to `get_default_aggregator()`:
   ```python
   return NewsAggregator(sources=[YFinanceNewsSource(), MyCustomSource()])
   ```

---

### [`backend/services/pump_classifier.py`](file:///home/jackc/projects/homma-research/backend/services/pump_classifier.py)
Two-phase classifier.

**Phase 1 — Lightweight (zero I/O):**
```python
stamp_catalyst_tags(gainers: list[dict]) -> list[dict]
```
Called on every 60-second screener refresh. Reads only existing in-memory fields. Preserves Phase 2 async-verified tags (never downgrades `Confirmed Catalyst` back).

**Phase 2 — Async Verification:**
```python
start_news_enrichment_loop(get_current_gainers_fn, interval_seconds=180)
```
Background daemon thread. Runs every 3 minutes during market hours (04:00–19:59 ET weekdays). Calls `NewsAggregator.has_news()` for all `Technical / No News` tickers. Upgrades tag to `Confirmed Catalyst` if news found. Writes result to `pump_classifications` table via upsert.

---

### [`backend/scripts/migrate_add_catalyst.sql`](file:///home/jackc/projects/homma-research/backend/scripts/migrate_add_catalyst.sql)
Already applied to the live database. Contains:
- `ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS catalyst TEXT`
- `CREATE TABLE IF NOT EXISTS pump_classifications (...)`

---

## 3. Modified Files

### [`backend/services/live_screener.py`](file:///home/jackc/projects/homma-research/backend/services/live_screener.py)
- `refresh_cache()`: calls `stamp_catalyst_tags(gainers)` after enrichment on every cycle
- `start_auto_persist()`: also launches `start_news_enrichment_loop()` with a lambda that returns `_cache['gainers']` by reference for in-place mutation

### [`backend/jobs/ingest_gainers.py`](file:///home/jackc/projects/homma-research/backend/jobs/ingest_gainers.py)
- `_enrich_ticker()`: calls `classify_catalyst()` after fetching the news headline; adds `catalyst` key to the returned dict
- `write_gainers()`: includes `catalyst` in the `INSERT` column list; calls `_persist_pump_classification()` after each successful insert
- `_persist_pump_classification()`: new helper that upserts to `pump_classifications` with `news_source='ingest_pipeline'`

### [`frontend/lib/api.ts`](file:///home/jackc/projects/homma-research/frontend/lib/api.ts)
```typescript
// Added to LiveGainerRow:
catalyst?:  string | null   // 'Confirmed Catalyst' | 'Technical / No News' | 'Speculative'
```

### [`frontend/components/LiveGainers.tsx`](file:///home/jackc/projects/homma-research/frontend/components/LiveGainers.tsx)
Two UI changes:

**1. Table row ticker badges** (alongside RR, FT, HOD):
```
⚠️ NNP  ← orange, tooltip: "No-News Pump — speculative volatility, no fundamental catalyst"
? SPEC   ← gray, tooltip: "Speculative — low/unknown RVOL, no confirmed catalyst"
```

**2. Headline drawer section:**
```
Confirmed Catalyst + headline  → italic gray headline text (unchanged)
Technical / No News            → orange ⚠️ "Speculative Volatility / No News" badge + subtext
Speculative                    → gray "? Unconfirmed Momentum" badge + subtext
null catalyst                  → "No recent news" (fallback, unchanged)
```

---

## 4. Database Schema (Applied)

```sql
-- Column on daily_gainers
catalyst TEXT   -- 'Confirmed Catalyst' | 'Technical / No News' | 'Speculative' | NULL

-- New table
pump_classifications (
    id             SERIAL PRIMARY KEY,
    ticker         TEXT        NOT NULL,
    date           DATE        NOT NULL,
    catalyst_tag   TEXT        NOT NULL,
    gap_pct        NUMERIC(8,2),
    rvol           NUMERIC(8,2),
    float_shares   BIGINT,
    classified_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    news_source    TEXT,       -- 'lightweight_check' | 'yfinance_verify' | 'ingest_pipeline'
    UNIQUE (ticker, date)
);
```

Indexes: `idx_pump_class_date`, `idx_pump_class_ticker`, `idx_pump_class_tag`

---

## 5. Deployment Steps

**Restart the FastAPI backend** to launch the enrichment loop:
```bash
sudo pm2 restart fastapi-backend
```

The `start_auto_persist()` call in `live_screener.py` now also fires `start_news_enrichment_loop()`, so the background thread starts automatically on uvicorn startup.

No frontend rebuild needed if running in dev mode. If production:
```bash
cd /opt/trading-journal/frontend && sudo npm run build
sudo pm2 restart nextjs-frontend
```

---

## 6. Future: Plugging In Your Custom News Aggregator

When you're ready to build an in-house news aggregator, the only file you need to touch is [`news_aggregator.py`](file:///home/jackc/projects/homma-research/backend/services/news_aggregator.py):

```python
class MyCustomNewsSource(NewsSource):
    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        # Call your own scraper / API here
        # Return list of {'title': ..., 'published': ..., 'source': ..., 'description': ...}
        ...

def get_default_aggregator() -> NewsAggregator:
    return NewsAggregator(sources=[
        YFinanceNewsSource(),
        MyCustomNewsSource(),   # ← add here
    ])
```

The `pump_classifier.py`, `live_screener.py`, and all UI code need **zero changes**.

---

## 7. Backtesting the pump_classifications Table

Query historical no-news pumps:
```sql
-- All 'Technical / No News' pumps this month
SELECT ticker, date, gap_pct, rvol, news_source
FROM pump_classifications
WHERE catalyst_tag = 'Technical / No News'
  AND date >= date_trunc('month', CURRENT_DATE)
ORDER BY gap_pct DESC;

-- Compare tier distribution
SELECT catalyst_tag, COUNT(*) as count, AVG(gap_pct) as avg_gap, AVG(rvol) as avg_rvol
FROM pump_classifications
GROUP BY catalyst_tag
ORDER BY count DESC;
```
