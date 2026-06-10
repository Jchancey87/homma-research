# Scope: Milestone 4 — Performance Scoring API

## Target Files
- `/home/jackc/projects/homma-research/backend/fastapi_app/routers/alerts.py`

## Requirements
Modify the `/api/alerts/daily-summary` endpoint to calculate forward returns and excursions on-the-fly:
1. **Inputs & Candlestick Data**:
   - For each alert on the requested date, retrieve 1-minute candlestick data from the `price_history_1min` table for that symbol.
   - The query window for candles starts at the minute of the alert `date_trunc('minute', alert_time)` and extends up to 15 minutes after (i.e. `alert_time + interval '15 minutes'`).
2. **Forward Returns Calculation**:
   - Calculate forward returns at 1m, 3m, 5m, and 15m intervals.
   - Specifically, find the candle close price at `alert_time + 1 minute`, `alert_time + 3 minutes`, `alert_time + 5 minutes`, and `alert_time + 15 minutes` (aligning to the nearest completed minute).
   - If a specific minute candle is missing, use the closest available preceding candle close in the window, or return `null` if no candles are found.
   - Formula: `((candle_close - trigger_price) / trigger_price) * 100.0`
3. **Excursion Metrics (MFE / MAE) Calculation**:
   - Calculate Maximum Favorable Excursion (MFE): `((max_high_in_15m - trigger_price) / trigger_price) * 100.0`
   - Calculate Maximum Adverse Excursion (MAE): `((min_low_in_15m - trigger_price) / trigger_price) * 100.0`
   - These are calculated over all candles in the 15-minute window following the alert time.
4. **Performance & Return Schema**:
   - Include these calculated fields in the alert objects returned by the API.
