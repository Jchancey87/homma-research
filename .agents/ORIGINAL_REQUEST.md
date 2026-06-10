# Original User Request

## Initial Request — 2026-06-06T02:48:12Z

Optimize the real-time momentum alert triggers, enrich Telegram notification details with decision context, and upgrade the Alert Journal dashboard to calculate and display expectancy statistics and forward returns.

Working directory: /home/jackc/projects/homma-research
Integrity mode: benchmark

## Requirements

### R1. Trigger Quality Optimizations (`stream_client.py`)
Tuning and improvement of real-time Schwab stream alert triggers to prevent noise:
- **HOD Breakout**: Enforce body-close breakouts (close of 1-minute candle above previous HOD) rather than simple wick breakouts.
- **Volume Spike**: Implement time-of-day adjusted relative volume or baseline normalization.
- **VWAP Crossover**: Implement volatility-based or ATR-based hysteresis instead of a static 2.0% buffer.
- **Volatility Halts/Resumes**: Implement a post-halt re-entry suppression window (e.g. 2 minutes) to prevent immediate duplicate crossover/HOD triggers.

### R2. Actionable Telegram Alerts (`tasks/alerts.py`)
Enrich Telegram breakout messages with comprehensive data:
- Include symbol, alert type, price, daily % change, candle volume vs. average, RVOL, float size/category, market cap, and relative VWAP/PDH distance.
- Preserve TradingView chart hyperlinks for all symbols.

### R3. Performance & Expectancy Feedback Loop
Upgrade the Alert Journal into a statistical performance engine:
- **Backend API (`routers/alerts.py`)**: Calculate forward returns (1m, 3m, 5m, 15m) and excursions (Maximum Favorable Excursion [MFE], Maximum Adverse Excursion [MAE]) on-the-fly using 1-minute TimescaleDB candlestick data for each alert.
- **Frontend UI (`alerts/page.tsx`)**: Render forward returns and excursion metrics next to alerts. Add a performance scorecard summarizing win rates, expectancy, and return rankings sorted by trigger type, price bucket, and float category.

## Acceptance Criteria

### Alert Trigger Quality
- [ ] HOD Breakouts require body close confirmation on 1-minute bars to trigger.
- [ ] VWAP Crossover alerts utilize a dynamic volatility/ATR-based hysteresis band.
- [ ] duplicate alerts are suppressed for 2 minutes immediately following volatility resumes.

### Alert Payload Formatting
- [ ] Telegram alert messages contain Price, daily % change, candle volume, RVOL, float, cap, VWAP/PDH relationship, and TV chart links.

### Performance Scoring
- [ ] Backend endpoint `/api/alerts/daily-summary` returns calculated forward returns (1m, 3m, 5m, 15m) and MFE/MAE values for each alert.
- [ ] Alert Journal page displays a win rate and expectancy scorecard categorized by alert type, price range, and float size.
- [ ] All unit tests pass cleanly, and the Next.js production build completes with 0 warnings.
