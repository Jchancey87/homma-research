---
name: alerts-hysteresis
description: Rules for alert state machines, cooldown functions, priority scoring, correlation grouping, and suppressions.
---

# Alerts & Hysteresis State Machine

## Database Cooldown Engine
* **Function:** `alerts.should_fire_alert(symbol, alert_type, price, ...)` in PostgreSQL.
* **Hysteresis State:** VWAP crossover maintains 'above' / 'below' state with ±2.0% buffer to prevent chattering.

## Priority Tiers & Scoring
* **Priority Score:** Computed via `calculate_confluence_score()` in `stream_client.py` (range 0–100).
* **Tiers:**
  * **Tier 1:** Score >= 75 (High priority Telegram dispatch).
  * **Tier 2:** Score >= 45.
  * **Tier 3:** Score < 45 (DB log only).

## Correlation & Suppression
* **Grouping (`group_id`):** Alerts on the same ticker within a 30s rolling window share a generated `group_id` UUID.
* **Already In Play (`ALREADY_IN_PLAY`):** Suppresses lower/equal priority alerts if Tier 1 or Tier 2 has already fired during the session for that symbol, unless price advances >5.0% beyond initial alert.
* **Post-Halt Suppression:** Suppresses momentum triggers for 120 seconds post volatility resume (`VOLATILITY_RESUME`).
