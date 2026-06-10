# Scope: Milestone 3 — Actionable Telegram Alerts

## Target Files
- `/home/jackc/projects/homma-research/backend/fastapi_app/tasks/alerts.py`

## Requirements
Enrich Telegram breakout alerts with comprehensive data and format them cleanly:
1. **Details to include**:
   - Symbol (as a TradingView hyperlink).
   - Alert type.
   - Price.
   - Daily % change (from previous close).
   - Candle volume vs. average (especially for Volume Spike, or if candle metrics are available).
   - RVOL.
   - Float size (shares outstanding) and float category (e.g. Micro, Small, Mid, Large).
   - Market Cap.
   - Relative VWAP distance (percentage above/below VWAP) and relative PDH (Previous Day High) distance.
2. **Hyperlinks**:
   - All symbols must have TradingView chart hyperlinks preserved: `[TICKER](https://www.tradingview.com/chart/?symbol=TICKER)`. Make sure to avoid escaping issues in markdown.
3. **Format**:
   - Use proper emoji, clean layout, and structured text to make the alerts actionable.
