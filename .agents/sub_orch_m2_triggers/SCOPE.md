# Scope: Milestone 2 — Trigger Quality Optimizations

## Target Files
- `/home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py`

## Requirements
Implement Schwab stream alert triggers tuning to prevent noise:
1. **HOD Breakout**: Enforce body-close breakouts (close of 1-minute candle above previous HOD) rather than simple wick breakouts. Wait for a 1-minute bar to complete, and check if its close is > the previous high of day.
2. **Volume Spike**: Implement time-of-day adjusted relative volume or baseline normalization (e.g. adjust relative volume calculation to handle pre-market vs regular session baselines, or implement time-of-day normalization).
3. **VWAP Crossover**: Implement volatility-based or ATR-based hysteresis instead of a static 2.0% buffer. Hysteresis band should adapt to the ticker's ATR or historical volatility.
4. **Volatility Halts/Resumes**: Implement a post-halt re-entry suppression window (2 minutes) to prevent immediate duplicate crossover or HOD breakout triggers.

## Interface Contracts & Guidelines
- Ensure that you follow the guidelines in `AGENTS.md` and `AGENT_MEMORY.md`.
- DO NOT hardcode test results. Implement genuine logic.
- Verify using local tests after changes.
