## 2026-06-06T02:50:00Z
**Context**: We are implementing Milestone 4 (Performance Scoring Backend API) in backend/fastapi_app/routers/alerts.py. We need to calculate forward returns (1m, 3m, 5m, 15m) and MFE/MAE on-the-fly inside the /api/alerts/daily-summary endpoint.
**Identity**: You are an Explorer subagent (Explorer 1). Your working directory is /home/jackc/projects/homma-research/.agents/explorer_m4_perf_api.
**Objective**:
1. Investigate the schema of price_history_1min in the database.
2. Check existing queries or usage of price_history_1min in the codebase.
3. Design an efficient query strategy to retrieve the 15-minute candlestick windows (from alert_time to alert_time + 15 minutes inclusive or trunc/rounding alignment as specified in SCOPE.md) for alerts on the requested date.
4. Define the exact Python/SQL algorithms to calculate:
   - Forward returns at 1m, 3m, 5m, and 15m (nearest completed minute. If a minute candle is missing, use the closest available preceding candle close in the window, or null if no candles are found).
   - MFE (Maximum Favorable Excursion): ((max_high - trigger_price) / trigger_price) * 100.0
   - MAE (Maximum Adverse Excursion): ((min_low - trigger_price) / trigger_price) * 100.0
5. Analyze any potential timezone/timestamp comparison issues (e.g. Postgres TIMESTAMPTZ comparison in asyncpg).
6. Write your findings to /home/jackc/projects/homma-research/.agents/explorer_m4_perf_api/analysis.md and send a status update.
