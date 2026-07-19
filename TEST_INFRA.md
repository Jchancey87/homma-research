# E2E Test Infrastructure Specification

## 1. Test Philosophy

Opaque-box testing. Tests interact only through external interfaces:
- HTTP API endpoints (via httpx AsyncClient)
- Database state (via asyncpg pool)
- Redis pub/sub channels
- Celery task payloads (mocked)

No internal implementation details are accessed. Tests validate observable
behavior: given specific inputs, does the system produce expected outputs?

## 2. Feature Inventory

| ID | Feature | Source Contract | Test Surface |
|----|---------|----------------|--------------|
| R1 | Trigger Quality Optimizations | `SchwabStreamer.on_level1_equity_message` | DB inserts into `screener_alerts`, Redis `screener:alerts` channel, Celery task dispatch |
| R2 | Actionable Telegram Alerts | `send_telegram_alert_task` Celery task | Telegram API call payload (mocked httpx.post) |
| R3 | Performance & Expectancy Feedback Loop | `compute_daily_summary`, `compute_performance_scorecard` | API responses: `GET /api/alerts/daily-summary`, `GET /api/alerts/performance` |

## 3. Test Architecture

### 3.1 Directory Layout
```
backend/tests/e2e/
    __init__.py
    conftest.py                  # E2E-specific fixtures
    mock_stream_generator.py     # Schwab Level 1 quote simulator
    test_cases.py                # All Tier 1-4 test cases
```

### 3.2 Tier Definitions

| Tier | Purpose | Count Target |
|------|---------|-------------|
| 1 | Feature Coverage | >= 20 tests (R1: 7, R2: 6, R3: 7) |
| 2 | Boundary & Corner Cases | >= 20 tests (R1: 7, R2: 6, R3: 7) |
| 3 | Cross-Feature Combinations | >= 4 tests |
| 4 | Real-world Application Scenarios | >= 5 tests |

**Total target: >= 49 tests**

### 3.3 Mocking Strategy

| External System | Mock Layer | Technique |
|----------------|------------|-----------|
| Schwab Stream API | `mock_stream_generator.py` | Dataclass-based quote builder, no network I/O |
| Redis Pub/Sub | `fakeredis.aioredis` | In-memory Redis substitute |
| Celery Tasks | `unittest.mock.patch` | Intercept `celery_app.send_task` |
| Telegram Bot API | `unittest.mock.patch` | Intercept `httpx.post` to `api.telegram.org` |
| PostgreSQL | Real DB via session pool | Seeded per-test data, cleaned by transaction rollback |

## 4. Setup Instructions

### 4.1 Prerequisites
- Python 3.11+
- PostgreSQL with TimescaleDB extension
- Redis server (for Celery broker, or use fakeredis)
- All backend dependencies installed (`pip install -r backend/requirements.txt`)

### 4.2 Running E2E Tests
```bash
cd backend
pytest tests/e2e/ -v
```

### 4.3 Environment Variables
Tests use the same env vars as the main app:
- `DATABASE_URL` / `ASYNCPG_DSN` — PostgreSQL connection
- `CELERY_BROKER_URL` — Redis for Celery (optional, fakeredis used in tests)
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — Mocked in tests

### 4.4 Database Seeding
E2E tests seed data directly via asyncpg:
1. `stock_fundamentals` — company metadata for alert enrichment
2. `screener_alerts` — alert records for daily-summary and scorecard queries
3. `price_history_1min` — 1-min candle data for forward return calculations

## 5. Interface Contracts

### 5.1 Alert Payload (Schwab Stream -> Redis -> Celery)
```json
{
  "symbol": "TICKER",
  "price": 12.34,
  "volume": 123456,
  "rvol": 2.5,
  "gap_pct": 5.2,
  "float_shares": 50000000,
  "alert_type": "NEAR_HOD_RADAR",
  "time": "2026-06-05T21:48:29.000Z"
}
```

### 5.2 Daily Summary Response
```json
{
  "date": "2026-06-05",
  "tickers": [
    {
      "symbol": "TICKER",
      "company_name": "Test Corp",
      "float_category": "Low-Float",
      "alerts": [
        {
          "id": 1,
          "alert_time": "...",
          "trigger_price": 12.34,
          "fwd_1m": 0.5,
          "fwd_5m": 1.2,
          "mfe": 2.1,
          "mae": -0.8
        }
      ]
    }
  ]
}
```

### 5.3 Performance Scorecard Response
```json
{
  "days": 30,
  "scorecard": [
    {
      "alert_type": "NEAR_HOD_RADAR",
      "price_bucket": "$5-15",
      "float_category": "Low-Float",
      "sample_count": 42,
      "avg_fwd_5m": 1.23,
      "win_rate_5m_pct": 58.3,
      "avg_mfe_pct": 3.45,
      "avg_mae_pct": -1.12
    }
  ]
}
```

## 6. Test Naming Convention

```
test_{tier}_{feature}_{scenario}
```

Example: `test_t1_r1_hod_breakout_body_close_suppression`

## 7. Failure Expectations

Since the actual feature implementations (M2-M5) have not landed yet, test
assertions are expected to FAIL on unimplemented logic. Tests must:
- **Compile** without import/syntax errors
- **Run** without fixture/setup errors
- **Fail** cleanly on assertion mismatches (not on missing functions/tables)

This allows incremental development: implement a feature, re-run tests,
watch assertions flip from FAIL to PASS.
