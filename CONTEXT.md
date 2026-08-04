# Homma Research Domain Context & Glossary (CONTEXT.md)

This document provides concise definitions of project-specific terms to ensure agent alignment and token-efficient communication.

## Glossary & Domain Concepts

* **Gainer:** A stock meeting live screener criteria at scan time (typically gap % >= 5%, price $0.50–$100, high RVOL). The raw candidate pool the screener evaluates.
  _Avoid_: Runner (when referring to a screener input state)

* **Runner:** A Continuation Journal performance outcome label. A symbol that sustained or extended momentum the following session. One of five outcome states: Runner, Win, Flat, Fade, Active.
  _Avoid_: Gainer (when referring to a post-hoc outcome)
* **RVOL (Relative Volume):** Ratio of current volume against 10-day volume baseline. Calculated using a piecewise intraday cumulative volume fraction U-curve (`_get_cumulative_volume_fraction`) rather than linear session progress.

* **Trading Session:** A single market day, divided into three phases (all US/Eastern): Pre-market 04:00–09:30, Regular 09:30–16:00, Post-market 16:00–20:00. AIP state, RVOL baselines, and HOD are all scoped per Trading Session and reset at the start of each new one.
  _Avoid_: "session" alone (ambiguous with agent session in AGENT_MEMORY.md)

* **MTF_IN_PLAY (Multi-Timeframe In Play):** A dynamic scanner state assigned to a symbol when its Multi-Timeframe S/R Momentum score reaches 60+. Distinct from the session-scoped AIP (Already In Play) alert-suppression flag.
  _Avoid_: "In Play" (without specifying MTF context) or "AIP"

* **HOD / NEAR_HOD_RADAR:** High of Day. `NEAR_HOD_RADAR` fires when a 1m candle completes with close exceeding the previous Trading Session high with RVOL >= 1.5.
* **VWAP Hysteresis:** State machine ('above' / 'below') tracking price relative to Volume Weighted Average Price with a 2.0% buffer to eliminate chatter on noise ticks.

* **Priority Score:** A 0–100 numeric score computed by the Confluence Score engine for each Alert Candidate. Reflects signal strength based on alert type weight, RVOL level, float category, market session, watchlist membership, and catalyst tags.
  _Avoid_: Confluence Score (that is the engine; Priority Score is its output on a per-alert basis)

* **Alert Tier:** A label bucketed from the Priority Score. Three values: Tier 1 (score ≥ tier1_threshold, default 75) — strongest signal; Tier 2 (score ≥ tier2_threshold, default 45) — moderate signal; Tier 3 (score < tier2_threshold) — weak or no signal. The AIP Check only suppresses when the original alert was Tier 1 or Tier 2.
  _Avoid_: Catalyst Tier (separate LLM concept, see below)
* **Already In Play (AIP):** A session-scoped state a symbol enters once a Tier 1 or Tier 2 alert has fired for it. Evaluated by the AIP Check gate in the alert pipeline.
  _Avoid_: "suppressed", "blocked" (AIP is a state, not an action)
* **Slow Path (Screener):** The 60-second screener cycle. Rebuilds the full candidate pool by calling Schwab Movers + TradingView + watchlists via REST. Source of truth for structural fields: gap %, float, price, RVOL baseline. Caps pool at 150 symbols.
  _Avoid_: "full path", "REST path"

* **Fast Path (Screener):** The 2-second screener cycle. Applies live Redis WebSocket ticks (`screener:quotes`) to the candidate pool last built by the Slow Path. Only price and volume fields refresh; structural fields (gap %, float) remain frozen from the last Slow Path cycle. Alert Candidates generated on the Fast Path use stale structural data.
  _Avoid_: "tick path", "WebSocket path"
* **Warrior Pattern:** A technical price-action setup detected by the Warrior Pattern Engine. Four types: `BULL_FLAG`, `VWAP_RECLAIM`, `MICRO_PULLBACK`, `PSYCH_BREAKOUT`. Full detection thresholds live in the `warrior-patterns` agent skill — do not duplicate them here.

* **Pattern Score:** An integer output of the Warrior Pattern Engine reflecting how many patterns are simultaneously active on a symbol. Returned alongside `active_patterns` in a `PatternResult`.
  _Avoid_: Priority Score (unrelated; that is the Confluence engine output)
* **Continuation Journal:** Tracking system recording next-day momentum performance of Gainer picks. Composed of two tables: `continuation_picks` (per-symbol outcome records) and `continuation_reflections` (nightly Reflections). Outcome states: Runner, Win, Flat, Fade, Active.

* **Reflection:** An LLM-generated nightly document produced from that day's Continuation Journal outcomes. Contains two components: `reflection_text` (prose post-mortem) and `lessons_json` (structured lesson list). Lessons are fed back into the next day's LLM continuation analysis as context.
  _Avoid_: "notes", "summary" (a Reflection is a structured feedback artifact, not freeform commentary)
* **Alert Candidate:** An un-suppressed alert trigger produced by pure evaluation of strategy rules. Has not yet passed validation gates.
  _Avoid_: Alert Signal (before gates pass)

* **Cooldown Check:** First gate in the alert pipeline. A database stored-procedure rate-limits repeated alerts on the same symbol within a configurable time window. Candidate fails here if the symbol fired too recently.

* **AIP Check (Already In Play Check):** Second gate in the alert pipeline. Suppresses a Candidate if a Tier 1 or Tier 2 alert already fired for that symbol this session, unless price has moved >5% from the initial alert price.

* **Alert Signal:** A validated, persisted, and dispatched alert event. Only produced after an Alert Candidate passes both the Cooldown Check and the AIP Check in sequence.
  _Avoid_: Alert Candidate (after gates pass)
* **Alert Review:** End-of-day (or historical) post-mortem of alert system performance. A live-queryable page (`/alert-review`) showing top gainers with alert markers overlaid, split into two sections: alerted symbols (sorted by MFE) and non-alerted gainers (sorted by gain %). Not a static capture — computed on the fly from `screener_alerts` + `price_history_1min`.
* **MFE (Maximum Favorable Excursion):** The maximum percentage price moved *in favor* (upward from trigger price) within a measurement window after an alert fired. Computed at 5m, 15m, 30m, and EOD intervals. The 15-minute MFE is the headline system quality metric.
* **MAE (Maximum Adverse Excursion):** The maximum percentage price moved *against* (downward from trigger price) within a measurement window after an alert fired. Same intervals as MFE. Indicates worst-case drawdown risk from acting on an alert.

* **Catalyst Tier:** An LLM-assigned label rating the quality of the news event driving a Gainer. Three values: Tier 1 — binary event with clear resolution (FDA, earnings, acquisition); Tier 2 — soft catalyst (contract win, partnership, analyst upgrade); Tier 3 — no real catalyst (vague press release, sector hype, unknown). Distinct from Alert Tier, which is a signal-strength bucket derived from Priority Score.
  _Avoid_: Alert Tier (when referring to LLM catalyst quality); "priority tier" (reserved for Alert Tier)

* **Float Category:** A bucket label classifying a symbol's public float (shares available to trade). Four values used by the Confluence engine: `Micro-Float` (<5M shares, highest Priority Score bonus), `Low-Float` (5M–20M), `Mid-Float` (20M–100M), `High-Float` (>100M). Used as an analytics dimension in Alert Review and Continuation Journal groupings.
  _Avoid_: "float tier" (use Float Category)

* **Alert Type:** A string identifier classifying what triggered an Alert Candidate (e.g., `NEAR_HOD_RADAR`, `VOLUME_SPIKE`, `VWAP_RECLAIM`, `VOLATILITY_HALT`). Each Alert Type carries a base weight in the Confluence Score engine. Used as a primary grouping dimension in alert analytics.
  _Avoid_: "alert name", "signal type"

* **Feedback Score:** A manual rating applied by the user after reviewing a fired Alert Signal. Stored alongside `feedback_notes` on the alert record. Used to measure human-assessed signal quality independently of the automated MFE/MAE metrics.
  _Avoid_: "rating", "grade"
