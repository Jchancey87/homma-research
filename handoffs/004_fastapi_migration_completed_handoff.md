# Handoff: FastAPI Migration Completed & Next Steps

This document outlines the current state of the repository, the completed FastAPI migration (Phases 1–5), and the roadmap/tasks for the next phase of development: **Schwab API Momentum Screener Integration**.

---

## 1. Project Status Summary

We have successfully migrated the backend from the legacy Flask implementation to a modern, fully asynchronous FastAPI backend. 

### Key Accomplishments
- **FastAPI Core**: Successfully transitioned all endpoints to FastAPI on port `5000`.
- **Celery & Redis**: Integrated a Celery task queue backed by Redis to manage heavy processing tasks (LLM deep research and scraping) out-of-thread.
- **APScheduler**: Configured the scheduler directly inside the FastAPI lifespan to handle scheduled tasks (e.g., nightly ingestion).
- **Clean Deprecation**: Removed all legacy Flask files (`app.py`, `routes/`), and dropped unused libraries (`flask`, `flask-cors`, `gunicorn`) from requirements.
- **Production Deployment**: Configured and deployed the new server architecture on the production VM using PM2 (`fastapi-backend`, `celery-worker`, and `nextjs-frontend`).

---

## 2. Current Architecture & Configurations

### PM2 Ecosystem
The production server processes are defined in `/opt/trading-journal/ecosystem.config.js` and managed via PM2:
1. **`fastapi-backend`**: Runs the FastAPI app using `uvicorn` on port `5000`.
2. **`celery-worker`**: Runs the background task processor executing tasks defined in `fastapi_app/celery_app`.
3. **`nextjs-frontend`**: Next.js client running on port `3000` (pointing to port `5000` for API endpoints).

### Database Layers
- **Async DB Access**: FastAPI routers use the `asyncpg` pool defined in `fastapi_app/db.py`.
- **Sync / Script Access**: Legacy scripts and ingestion processes still use the synchronous wrapper in `database.py` utilizing `psycopg2`.

---

## 3. Next Phase: Schwab API Momentum Screener Integration

Now that the async platform is stable and clean, the next step is implementing the real-time Ross Cameron-style momentum screener leveraging the **Schwab Trader API**.

### Roadmap & Tasks

#### Task 1: Complete Schwab WebSocket Client (`schwab/stream_client.py`)
- Implement real-time Level 1 quote streaming.
- Subscribe candidates to Level 1 updates and 1-minute OHLCV candles.
- Register stream handlers (`on_quote_update`, `on_candle_update`) to capture intraday ticks.

#### Task 2: Real-time Momentum Filters (`screener/filters.py`)
- Apply Ross Cameron filters on quote stream updates:
  - Price: `$2.00 – $20.00`
  - Relative Volume: `> 2.0x`
  - Float classification: Nano/Low (`< 50M` shares)
  - Pre-market gap: `> 5%` (or `> 10%` for high-probability setups)

#### Task 3: In-Memory VWAP Tracker (`screener/vwap.py`)
- Implement a stateful accumulator to calculate volume-weighted average price (VWAP) in real-time from the 1-minute candle stream.
- Trigger breakout alerts when a candidate stock crosses above VWAP.

#### Task 4: Dynamic Watchlist/Stream Management
- Automatically add new high-momentum candidates discovered by the pre-market scanner to the live WebSocket subscription pool.
- Automatically prune cold symbols (low relative volume, or price drifting outside filter boundaries) to conserve WebSocket bandwidth.

#### Task 5: Rich Discord/Telegram Notification Card
- Integrate Discord webhook client to push rich notification cards featuring price details, float metrics, relative volume ratio, gap percentage, short interest, and IV percentile.

---

## 4. Local Development Cheat Sheet

### Starting the Dev Session (via tmux)
```bash
./start_journal.sh
```
This spawns 4 tmux windows:
- **`0: backend`**: FastAPI app on port `5000` with live reload.
- **`1: frontend`**: Next.js development server.
- **`2: scripts`**: Shell pre-activated with the backend virtual environment.
- **`3: celery`**: Celery worker instance outputting log events.

### Running Integration Tests
Ensure the database and environment variables are active, then run:
```bash
python3 -m pytest tests/ -v -s -p no:anyio
```
