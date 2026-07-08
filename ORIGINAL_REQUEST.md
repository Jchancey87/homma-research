# Original User Request

## Initial Request — 2026-07-08T07:48:42-05:00

Rework the momentum trading alert system in a day trading research platform to be production-grade, aligned with Ross Cameron / Warrior Trading style momentum strategies. The current system has 6 active alert types with hardcoded thresholds, no priority tiers, no confluence scoring, and fires only for manually watchlisted tickers. The rework adds 5 new alert types, a 3-tier priority system with confluence scoring, an admin UI for threshold tuning, distinct audio per alert type, strategy labeling, and removes the watchlist-only gate so alerts fire for ALL qualifying screener tickers.

Working directory: ~/teamwork_projects/alert_system_rework
Integrity mode: development

Reference codebase (read-only source of truth): /home/jackc/projects/homma-research

## Context: Current Architecture

The existing alert pipeline flows through these stages:
1. **Detection**: Schwab WebSocket → `momentum_screener/schwab/stream_client.py` (real-time Level 1 equity data)
2. **Filtering/Cooldown**: `check_and_fire_alert()` with Postgres function `alerts.should_fire_alert()` + in-memory halt cooldown
3. **Persistence**: INSERT into `screener_alerts` (TimescaleDB hypertable)
4. **Dispatch**: Redis pub/sub (`screener:alerts` channel) + Celery task for Telegram
5. **Delivery**: Telegram messages (Celery worker) + Frontend SSE (Redis → `/api/alerts/stream` → `useAlertStream.ts` hook → toast + audio + row flash)
6. **Review**: Alert Journal page (`alerts/page.tsx`) with interactive charts, forward returns, feedback system, performance scorecard

Key files to study in the reference codebase:
- `momentum_screener/schwab/stream_client.py` — all detection logic, ~800 lines
- `backend/fastapi_app/tasks/alerts.py` — Telegram formatting & dispatch
- `backend/fastapi_app/routers/alerts.py` — SSE endpoint + alert CRUD
- `backend/fastapi_app/db/screener_alerts.py` — DB queries
- `backend/sql/alerts_cooldown_multi_type.sql` — Postgres cooldown function
- `backend/services/alerts_analytics.py` — forward returns, mfe/mae
- `backend/services/pump_classifier.py` — catalyst tagging (3 tiers)
- `backend/services/live_screener.py` — screener cache, background refresh
- `frontend/components/live-gainers/useAlertStream.ts` — SSE client, audio, flash
- `frontend/components/ToastStack.tsx` — toast notification UI
- `frontend/app/alerts/page.tsx` — Alert Journal page (~940 lines)
- `backend/config.py` — Settings/Config classes
- `backend/fastapi_app/scheduler.py` — APScheduler jobs (pre-market summary, etc.)

Existing test suite: 266 tests in `backend/tests/` (run with `/opt/trading-journal/backend/venv/bin/pytest -p no:anyio`)

## Requirements

### R1. Fix Critical Bugs

Five bugs must be fixed before any new features:
1. `gap_pct` calculation uses `low_52wk` as prev_close (stream_client.py:467) — must use actual previous day close
2. `screener_alerts.sent` column is never set to TRUE after Telegram delivery
3. Frontend price filter ($2–$25 in LiveGainers.tsx) does not match backend ($1–$30) — unify them
4. `ALERT_MIN_PCT_INCREASE` env var in config.py is never used — either wire it in or remove it
5. `short_int_float` column in screener_alerts is never populated — populate it or remove it

### R2. Tiered Alert Priority System with Confluence Scoring

Implement a 3-tier priority system driven by a confluence scoring engine:

- **Tier 1 (Critical)**: High-conviction setups. Delivered via Telegram + distinct loud audio chime + prominent toast. Requires multiple confluent signals (e.g., HOD breakout + volume surge + high RVOL + catalyst confirmed).
- **Tier 2 (Priority)**: Setup forming, needs manual chart review. Delivered via toast notification + subtle audio chime. Single strong signal or partial confluence.
- **Tier 3 (Informational)**: Routine activity. Logged to database and visible in the Alert Journal, but no push notification or sound.

The scoring engine should assign a weighted composite score based on: number of confluent signals firing, RVOL strength, catalyst presence, float category, historical success rate of the alert type, and current market session (pre-market vs open vs afternoon). The tier is determined by score thresholds.

### R3. Five New Alert Types

Add these alert types to the detection engine:

1. **RUNNING_UP**: Catches rapid price surges before they officially make new HOD. Detect when price rises X% within Y candles on elevated volume.
2. **BULL_FLAG**: Identify bull flag / ABCD consolidation patterns. Squeeze up → brief pullback on declining volume → alert on first candle breaking consolidation high.
3. **VWAP_RECLAIM**: Re-enable and improve the disabled VWAP_BOUNCE. Alert when price reclaims VWAP from below with volume confirmation and rising VWAP slope.
4. **MULTI_TF_CONFLUENCE**: Alert when short-term signal (1-min) is confirmed by a longer timeframe level (5-min or 15-min support/resistance, EMA alignment).
5. **HALT_RESUME_MOMENTUM**: Post-halt continuation signal. When a halted stock resumes trading, detect if it immediately continues in the halt direction with volume.

Each new type must integrate with the existing pipeline (cooldown system, persistence, Telegram formatting, SSE delivery, Alert Journal markers).

### R4. Remove Watchlist-Only Gate

Currently `check_and_fire_alert()` requires the symbol to be in the user's watchlist. Remove this gate so alerts fire for ALL tickers on the live screener that meet the momentum criteria. Add an optional "watchlist priority boost" — watchlisted tickers get a +N score bonus in the confluence engine, making them more likely to reach Tier 1.

### R5. Admin UI for Alert Configuration

Build a frontend admin page (accessible from the app navigation) that allows tuning alert parameters without restarting services:

- Enable/disable each alert type individually
- Adjust thresholds per alert type (RVOL minimums, volume multipliers, price ranges, etc.)
- Set cooldown intervals per alert type
- Configure tier score thresholds (what score = Tier 1 vs 2 vs 3)
- Set the confluence weight for each signal factor
- Preview current config vs defaults
- Changes must persist to the database and be picked up by the streaming engine without restart (the streamer should poll or subscribe to config changes)

### R6. Strategy Labels and Context-Rich Alerts

Every alert (Telegram + frontend toast + journal) must include:
- **Strategy label**: Which pattern triggered (e.g., "Gap and Go", "Bull Flag Breakout", "VWAP Reclaim")
- **Confluence score**: Numeric score + tier badge
- **Context fields**: RVOL, float category, catalyst tag (from pump_classifier), VWAP distance %, distance from HOD/LOD
- **Suggested levels**: When determinable, include approximate stop level (e.g., low of consolidation for bull flag) and target (next resistance or % extension)

### R7. Distinct Audio Per Alert Type

Replace the single sine wave chime with distinct audio signatures per alert type/tier:
- Different tones, frequencies, or patterns so the trader can identify alert type without looking at the screen
- Tier 1 alerts should have a more urgent, attention-grabbing sound
- Tier 3 alerts should have no sound
- Audio should be generated via Web Audio API (no external audio files needed)

### R8. Production Quality

- All 266 existing backend tests must continue to pass
- New features must have test coverage: unit tests for the scoring engine, alert type detection logic, and config persistence
- Database migrations must be provided as SQL files (the project uses raw SQL migrations, not an ORM)
- The alert config admin API must follow the project's Router Layer Rules: routers are thin (parse → call service → format response), no business logic or raw SQL in routers, SQL lives in `db/` or `services/` modules
- Frontend changes must build successfully with the existing Next.js setup

## Acceptance Criteria

### Bug Fixes
- [ ] `gap_pct` in alert payloads uses actual previous day close price, not `low_52wk`
- [ ] After successful Telegram delivery, `screener_alerts.sent` is updated to TRUE
- [ ] Frontend and backend price filters use the same range
- [ ] `ALERT_MIN_PCT_INCREASE` is either wired into the detection logic or removed from config
- [ ] `short_int_float` is either populated from available data or the column is dropped

### Tiered Priority
- [ ] Alerts are classified into Tier 1, 2, or 3 based on a confluence score
- [ ] Tier 1 alerts are delivered via Telegram + loud audio + toast
- [ ] Tier 2 alerts are delivered via toast + subtle audio
- [ ] Tier 3 alerts are logged to DB and visible in Alert Journal but produce no notification
- [ ] The scoring engine considers at minimum: confluent signals, RVOL, catalyst, float, and market session

### New Alert Types
- [ ] RUNNING_UP, BULL_FLAG, VWAP_RECLAIM, MULTI_TF_CONFLUENCE, and HALT_RESUME_MOMENTUM are implemented
- [ ] Each new type appears in the Alert Journal with a distinct marker color/shape
- [ ] Each new type has Telegram formatting via ALERT_TYPE_META
- [ ] Each new type integrates with the cooldown system

### Configuration
- [ ] An admin page exists in the frontend navigation for alert configuration
- [ ] Alert types can be individually enabled/disabled from the admin UI
- [ ] Threshold values can be adjusted from the admin UI and take effect without service restart
- [ ] Config changes persist to the database

### Context & Sound
- [ ] Alert messages (Telegram + toast) include strategy label, confluence score, and context fields
- [ ] At least 3 distinct audio signatures exist (one per tier, or per alert category)
- [ ] Tier 1 and Tier 2 sounds are clearly distinguishable

### Quality
- [ ] All 266 existing backend tests pass
- [ ] New unit tests cover: scoring engine logic, each new alert type detection, config CRUD
- [ ] SQL migration files are provided for any schema changes
- [ ] No raw SQL or business logic in router files (Router Layer Rules compliance)
- [ ] Frontend builds successfully
