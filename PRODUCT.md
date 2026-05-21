# PRODUCT: Momentum Trading Dashboard

## Register: Product
(Observability dashboard / FinTech interface)

## Product Purpose
A high-signal "Morning Briefing" center for small-cap momentum traders. It transforms raw market data into actionable intelligence during the critical 4:00 AM – 9:30 AM pre-market window.

## Users
Solo day traders who need to filter 500+ daily gainers into a "Watchlist of 3" in under 30 minutes. They value speed, signal-to-noise ratio, and historical context over decorative charts.

## Strategic Principles
1. **Speed to Signal**: Critical metrics (Gap %, RVOL, Float) must be readable in <500ms.
2. **Context is King**: Every gainer should be cross-referenced with historical performance (Repeat Runners).
3. **Market Breadth First**: Trade in the direction of the tide (SPY/QQQ/Risk Bias).
4. **Follow-Through Awareness**: Identify if yesterday's momentum is continuing or fading.

## Features
- **Morning Briefing Header**: Contextual greetings and date/market status.
- **Market Breadth Bar**: Live index prices and derived Risk ON/OFF bias.
- **Repeat Runner Alerts**: Flags stocks moving today that have appeared in the DB before.
- **Float Bucket Summary**: Visual breakdown of which float tier (Nano/Micro/Small) is in play.
- **Sector Rotation**: Weekly vs last week performance tracking.
- **Economic Calendar**: High-impact events (CPI, FOMC) with countdown.
- **Watchlist with Live Prices**: Real-time monitoring of saved tickers with "Wake Up" alerts.
- **AI Continuation Picks**: Advanced screening for multi-day runners.

## Tone & Brand
- **Professional & Precise**: High density, low decoration.
- **Restrained Aesthetic**: Emerald accents for "in play" signals, otherwise monochromatic.
- **Trustworthy**: Data-driven, using professional APIs (Polygon, FMP).

## Feature Backlog / Request List
- **Schwab WebSocket Streamer**: Replace periodic HTTP polling with real-time Level 1 quote streaming client.
- **Stateful Screener Filters**: Add UI sliders/inputs on the frontend to filter gainers dynamically by float, price, and volume.
- **VWAP Tracker**: Add intraday volume-weighted average price calculation and show stock price relative to VWAP.
- **Discord Webhook Alerts**: Push real-time alerts to a Discord channel when new gainers meet the criteria.
