# Homma Research Domain Context & Glossary (CONTEXT.md)

This document provides concise definitions of project-specific terms to ensure agent alignment and token-efficient communication.

## Glossary & Domain Concepts

* **Runner / Gainer:** A stock experiencing high intraday price momentum (typically gap % >= 5%, price $0.50–$100, high RVOL).
* **RVOL (Relative Volume):** Ratio of current volume against 10-day volume baseline. Calculated using a piecewise intraday cumulative volume fraction U-curve (`_get_cumulative_volume_fraction`) rather than linear session progress.
* **HOD / NEAR_HOD_RADAR:** High of Day. `NEAR_HOD_RADAR` fires when a 1m candle completes with close exceeding previous session high with RVOL >= 1.5.
* **VWAP Hysteresis:** State machine ('above' / 'below') tracking price relative to Volume Weighted Average Price with a 2.0% buffer to eliminate chatter on noise ticks.
* **Already In Play (AIP):** Alert suppression mechanism. Prevents duplicate lower/equal tier alerts on a symbol once a Tier 1/2 alert has fired in a session, unless price moves >5% from initial alert price.
* **Fast/Slow Path Screener:** Two-tier polling architecture in `live_screener.py`. Fast path (2s) applies WebSocket Redis ticks (`screener:quotes`); slow path (60s) executes full REST pipeline.
* **Warrior Pattern Engine:** Module (`services/pattern_detector.py`) detecting Bull Flags, VWAP Reclaims, Micro Pullbacks, and Psychological Dollar breakouts.
* **Continuation Journal:** Tracking system (`continuation_picks`, `continuation_reflections`) logging next-day momentum performance outcomes (Runner, Win, Flat, Fade, Active) and nightly LLM reflection lessons.
* **Alert Candidate / Alert Signal:** `AlertCandidate` is an un-suppressed alert trigger produced by pure evaluation of strategy rules. `AlertSignal` is a validated, persisted, and dispatched alert event after passing database stored-procedure cooldown and AIP checks.
* **Alert Review:** End-of-day (or historical) post-mortem of alert system performance. A live-queryable page (`/alert-review`) showing top gainers with alert markers overlaid, split into two sections: alerted symbols (sorted by MFE) and non-alerted gainers (sorted by gain %). Not a static capture — computed on the fly from `screener_alerts` + `price_history_1min`.
* **MFE (Maximum Favorable Excursion):** The maximum percentage price moved *in favor* (upward from trigger price) within a measurement window after an alert fired. Computed at 5m, 15m, 30m, and EOD intervals. The 15-minute MFE is the headline system quality metric.
* **MAE (Maximum Adverse Excursion):** The maximum percentage price moved *against* (downward from trigger price) within a measurement window after an alert fired. Same intervals as MFE. Indicates worst-case drawdown risk from acting on an alert.

