# Agentic Memory & Reflections (`AGENT_MEMORY.md`) 🧠

This file acts as a persistent memory block where AI coding agents record prompt adaptations, debugging failures, architectural decisions, and key directives to prevent system drift across sessions.

---

## [2026-06-03] Real-Time Notification & Visual Alert System Implementation

### 1. Objective & Outcomes
* **Objective**: Add database rate-limiting and Telegram alerts for breakout events, plus a reactive Next.js UI showing visual highlights and audio chimes.
* **Deliverables**:
  - `alerts.ticker_cooldowns` table and `alerts.should_fire_alert` Postgres procedure.
  - Celery background task (`send_telegram_alert_task`) in FastAPI dispatching formatted bot messages via HTTP.
  - Next.js real-time event stream subscription, toast notifications card stack, fading background flashes in the Live Gainers grid, Web Audio plink chime synthesizer, and mute settings controls.

### 2. Prompt Adaptations & Alignments
* **Discrepancy Correction**: The user's architectural handoff file suggested a SvelteKit frontend. We cross-referenced the active workspace files and detected the frontend is Next.js (React + Tailwind). I raised this and rewrote the blueprints into React.
* **Architecture Clarifications**: I used an interactive Q&A "grill session" to clarify design decisions prior to implementation, allowing us to align on:
  1. Using Redis Pub/Sub for SSE but checking a DB stored procedure first.
  2. Running the Telegram dispatcher as a background Celery task to ensure zero lag on the Schwab streamer.
  3. Synthesizing audio cues dynamically via Web Audio API to bypass raw file path loading dependencies.

### 3. Mistakes & Self-Corrections
* **Venv Pathing during Tests**: A subagent encountered a `ModuleNotFoundError` during tests due to using standard python instead of the local production virtualenv (`/opt/trading-journal/backend/venv`). I corrected the python path, ensuring proper test execution.
* **Workspace vs. Production Decoupling**: During testing, we hit `0 active subscribers` in the Redis loop because the development workspace (`/home/jackc/projects/homma-research`) is completely decoupled from the production deployment folder (`/opt/trading-journal`). We staged, committed, and pulled the changes to synchronize production.
* **Typo in Env Keys**: The user copy-pasted their bot token but saved it as `TELEGRAM_BOT_TOKEN0`. We corrected the key to `TELEGRAM_BOT_TOKEN` in `.env` to fix the `401 Unauthorized` check.

### 4. Directives for Future Agents
* **Environment Configuration**: Always verify keys in the active `backend/.env` file. Check spelling carefully.
* **Screener Streamer Logging**: All screener alerts insert into `screener_alerts` and publish to the `screener:alerts` Redis channel.
* **Web Audio Synthesis**: In `LiveGainers.tsx`, use the browser Web Audio API `playPlinkChime` function to play alerts dynamically. Do not add raw audio file attachments.
* **Deployment Workflow**: Remember that code must be committed in `/home/jackc/projects/homma-research`, pulled into `/opt/trading-journal`, and deployed using `/opt/trading-journal/deploy.sh` to take effect.
