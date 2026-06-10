## 2026-06-05T21:50:14-05:00

You are a read-only exploration agent. Your working directory for coordination files is /home/jackc/projects/homma-research/.agents/explorer_m3_telegram/.
Your task is to:
1. Examine /home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py and understand the existing alert message format.
2. Examine the database schema and query mechanism in /home/jackc/projects/homma-research/backend/database.py. Check what columns and data are available in `stock_fundamentals`, `price_history_daily`, and `price_history_1min`.
3. Design the logic to fetch/calculate the following fields dynamically for a given symbol and alert time:
   - Daily % change (from previous close).
   - Float size (shares outstanding) and float category (e.g. Micro, Low, Mid, Large, nano, etc. See how it is categorized in stream_client.py or design a standard mapping).
   - Market Cap.
   - Relative VWAP distance (percentage above/below VWAP) at the alert time.
   - Relative PDH (Previous Day High) distance at the alert time.
   - Candle volume vs average (for Volume Spike).
4. Outline how to query the database using the synchronous `database.get_connection()` context manager. Provide SQL queries to retrieve:
   - Fundamentals (company_name, shares_outstanding, market_cap, float_category).
   - Previous close and Previous Day High (high) from `price_history_daily` (the most recent date < today's date).
   - Todays's intraday volume and price typical/close values from `price_history_1min` up to the alert time to compute VWAP.
   - The last completed 1-minute candle volume and the average volume of the previous 20 completed 1-minute candles for the VOLUME_SPIKE candle volume comparison.
5. Provide recommendations on how to format TradingView links cleanly: `[TICKER](https://www.tradingview.com/chart/?symbol=TICKER)`. Specifically address how to avoid escaping issues in Telegram Markdown.
6. Verify existing test files and run commands to test them.
7. Write your analysis and implementation plan to /home/jackc/projects/homma-research/.agents/explorer_m3_telegram/handoff.md. Use send_message to notify me when complete.
