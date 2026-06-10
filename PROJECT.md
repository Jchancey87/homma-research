# Project: Real-time Momentum Alerts & Statistical Journal Upgrades

## Architecture
This project modifies the momentum screener alert logic, Telegram notification layer, and Alert Journal dashboard.
- **Schwab Stream Client (`momentum_screener/schwab/stream_client.py`)**: Consumes live Level 1 equity quote updates, builds 1-minute volume and price candles in-memory, tracks technical states (HOD, VWAP), checks watchlist constraints, queries a Postgres stored procedure for cooldown checks, and triggers alerts.
- **Telegram Notification Worker (`backend/fastapi_app/tasks/alerts.py`)**: A Celery task worker that receives alert JSON payloads from the stream client, queries additional fundamentals/market data if needed, formats message payloads in markdown with TV hyperlinks, and posts to Telegram.
- **Alert API Router (`backend/fastapi_app/routers/alerts.py`)**: Adds statistical computations to the `/api/alerts/daily-summary` endpoint, fetching 1-minute TimescaleDB candlestick data to calculate forward returns (1m, 3m, 5m, 15m) and MAE/MFE on-the-fly.
- **Alert Journal UI (`frontend/app/alerts/page.tsx`)**: Displays the list of daily alerts, shows forward return and excursion metrics, and renders a performance scorecard classifying metrics by trigger type, price bucket, and float category.

## Code Layout
- `momentum_screener/schwab/stream_client.py` - Schwab streaming alerts engine
- `backend/fastapi_app/tasks/alerts.py` - Telegram alert formatting and delivery
- `backend/fastapi_app/routers/alerts.py` - Backend REST API endpoints
- `frontend/app/alerts/page.tsx` - Alert Journal UI and Scorecard dashboard

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| M1 | E2E Test Suite | Build E2E test infra and 49+ tests across Tiers 1-4. Publish `TEST_READY.md`. | None | IN_PROGRESS (Conv: f4572c1e-ae4c-47e1-921f-d3723d617215) |
| M2 | Trigger Quality Optimizations | Body-close HOD breakouts, TOD-adjusted RVOL, ATR-based VWAP crossover, post-halt re-entry suppression. | None | IN_PROGRESS (Conv: 819cf0d3-df71-49f6-9f17-986b6f6e3987) |
| M3 | Actionable Telegram Alerts | Enrich breakout message details, preserve TradingView links. | None | IN_PROGRESS (Conv: 5409f2c7-7b86-4215-b02c-29fbd6df8f08) |
| M4 | Performance scoring API | Calculate forward returns and MFE/MAE on-the-fly in `/api/alerts/daily-summary`. | None | IN_PROGRESS (Conv: 54e86b04-08ab-40a6-b59d-512872e9e62d) |
| M5 | Performance Dashboard & Scorecard | Render metrics on the Alert Journal dashboard page, add performance summary scorecard. | M4 | PLANNED |
| M6 | E2E Test Suite Pass | Run and pass 100% of E2E tests (Tiers 1-4) on implemented code. | M1, M2, M3, M4, M5 | PLANNED |
| M7 | White-box Adversarial Hardening | Generate Tier 5 tests to find gaps and bugs, fix and verify. | M6 | PLANNED |

## Interface Contracts
### Schwab Stream Client -> Redis & Celery
- Payload shape:
  ```json
  {
    "symbol": "TICKER",
    "price": 12.34,
    "volume": 123456,
    "rvol": 2.5,
    "gap_pct": 5.2,
    "float_shares": 50000000,
    "alert_type": "ALERT_TYPE",
    "time": "2026-06-05T21:48:29.000Z"
  }
  ```
- Active alert types: `HOD_BREAKOUT`, `VWAP_CROSSOVER`, `PREV_DAY_BREAKOUT`, `VOLUME_SPIKE`, `VOLATILITY_HALT`, `VOLATILITY_RESUME`. Note: `VWAP_BOUNCE` is disabled.

### Backend `/api/alerts/daily-summary` -> Frontend
- Returns array of objects with additional properties:
  ```typescript
  interface AlertRecordSummary {
    id: string;
    symbol: string;
    alert_time: string;
    trigger_price: number;
    trigger_volume: number;
    rel_vol: number;
    gap_pct: number;
    float_shares: number;
    alert_type: string;
    feedback_score?: string;
    feedback_notes?: string;
    company_name?: string;
    float_category?: string;
    market_cap?: number;
    // Metrics calculated on-the-fly:
    forward_return_1m?: number;
    forward_return_3m?: number;
    forward_return_5m?: number;
    forward_return_15m?: number;
    mfe_pct?: number;
    mae_pct?: number;
  }
  ```
