# Trading Pattern Journal 📈

A sophisticated, self-hosted trade journal and research platform designed for technical traders focused on small-cap breakouts, gap-and-go trades, and momentum archetypes. It is built to mimic high-density Bloomberg or Lightspeed trading terminals.

## 🚀 Overview

This platform automates the process of identifying, analyzing, and journaling market gainers. It combines high-performance interactive charting with a multi-module AI research engine and real-time streaming data pipelines to evaluate stock setups and calculate advanced momentum metrics in milliseconds.

## 🛠️ Technology Stack

- **Backend**: Python 3.12, FastAPI (Asynchronous lifespan), PostgreSQL (TimescaleDB), Celery, Redis
- **Frontend**: Next.js 14 (App Router), Tailwind CSS, [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- **AI/LLM**:
  - **Text**: Groq (Llama 3) for rapid structured analysis reports.
  - **Vision**: Gemini 1.5 Pro/Flash for automated chart annotation and pattern recognition.
- **Data Pipeline**: Schwab Trader API (Market data & Level 1 WebSocket), Financial Modeling Prep (FMP - Primary Fundamental/Earnings), SEC EDGAR (Filings & PIPE detection), finviz, yfinance
- **Deployment**: PM2 (Process Management), Nginx Proxy Manager, Docker Compose (PostgreSQL & Redis)

---

## ✨ Core Features

### 📊 Ross Cameron Momentum Scanners & Data Audit
- **All Live Gainers Scanner**:
  - Calculates daily overhead space to major EMAs (50, 200 EMA) and 20D resistance levels, displaying `"Blue Sky"` for breakout rooms.
  - Identifies catalyst tags (`NEWS`, `NO NEWS`, `SPEC`) based on live Schwab news headline parsing.
- **Near HOD Radar**:
  - `Pullbacks (PB)`: Counts consecutive red 1-minute candles to scan for coiling bull flags.
  - `EMA9 Dist`: Shows percentage distance from the 1-minute 9 EMA (highlights green when nestled, warning red when overextended).
  - `Psych Dist`: Shows the distance in cents to the next psychological whole or half dollar interval breakout wall (e.g., `+$3.00 (+8c)`).
- **High RVOL Radar**:
  - `Vol Ratio`: Calculates percentage of regular session volume generated during the opening 30-minute rush (9:30 AM–10:00 AM ET).
  - `1m RVOL`: Measures micro-candle tape acceleration against the 20-period average.
- **Risk Audit Badging**:
  - Highlights prices in the **$2.00–$10.00** momentum sweet spot, and pulses red for compliance/dilution risk under **$2.00**.
  - Warns of **"Float Blindness"** by displaying flashing red `UNVERIFIED` badges if the float metric fails to resolve, and colors micro-floats (<5M) fuchsia.
  - **Stop-Loss Calibration**: Displays absolute **ATR (1m)** and **Spread (Cents)** in the details drawer to verify if a tight 20-cent risk profile is structurally viable.

### ⏱️ Real-Time Breakout Alerts & SSE Stream
- **Visual Highlights**: Out-of-bounds breakouts flash neon amber rows on the dashboard with a 3.5s slow decay fade.
- **Audio Chimes**: Dynamic browser-synthesized audio chimes trigger on breakouts without requiring external assets.
- **Toast Notifications**: Stackable notifications with clickable actions that direct traders instantly to research screens.
- **Telegram Bot**: Broadcasts breakout alerts dynamically formatted with TradingView hyperlinks.

### 🔬 Interactive Deep Research
- **Full Report**: AI-generated reports reviewing fundamental health, ownership structures, and technical setups.
- **SEC Forensic Audits**: Scans SEC filings for reverse splits, shelf offerings (S-3), ATM distributions (424B), and toxic warrants.
- **Catalyst Ratings**: Automatically scores news events as Tier 1 (binary), Tier 2 (soft), or Tier 3 (none) with 8-K parsing.
- **Confluence Engine**: Computes setup scores (1–10) based on moving average structures, RS vs. SPY, and historical runners.

---

## ⚙️ Setup & Installation (Proxmox/Ubuntu LXC)

### Infrastructure Mapping

| Component | Target Address | Role / Description |
|---|---|---|
| **App Server** | `192.168.0.202` | Ubuntu LXC — Runs Next.js, FastAPI, Celery, and Streamer |
| **Database & Cache** | `192.168.0.201` | Proxmox VM — Runs PostgreSQL (TimescaleDB) and Redis |
| **Proxy** | Nginx Proxy Manager | Handles SSL certificates and public routing |

### 1. Prerequisites (Ubuntu LXC)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv nodejs npm git -y
```

### 2. Clone the Repository
```bash
git clone https://github.com/Jchancey87/Analysis-App.git /opt/trading-journal
cd /opt/trading-journal
```

### 3. Start Database & Redis (Host `192.168.0.201`)
Ensure Docker Compose is installed on the database server, then launch services:
```bash
docker-compose up -d
```

### 4. Configure Environment Files
Configure environment variables in `/opt/trading-journal/backend/.env`:
```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Key environment properties:
- `DATABASE_URL`: `postgresql://journal:journal@192.168.0.201:5432/trading_journal`
- `CELERY_BROKER_URL`: `redis://192.168.0.201:6379/0`
- `CELERY_RESULT_BACKEND`: `redis://192.168.0.201:6379/1`
- `SCHWAB_API_KEY` & `SCHWAB_API_SECRET`: Developer client credentials
- `SCHWAB_TOKEN_PATH`: `/home/jackc/.config/schwab/token.json` (allows shared OAuth token access)
- `LLM_API_KEY` (Groq), `GEMINI_API_KEY`, and `FMP_API_KEY`

### 5. Backend Environment Setup
```bash
cd /opt/trading-journal/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 6. Schwab API One-Time Auth Setup
To generate the required OAuth token, execute the interactive helper script:
```bash
python3 scripts/schwab_auth_setup.py
```
This utility walks through entering the Schwab authentication URL and capturing the response payload to write `token.json` into the configured path.

### 7. Frontend Build & Install
```bash
cd /opt/trading-journal/frontend
npx pnpm@9 install
npx pnpm@9 run build
```

---

## 🚀 Running the Application in Production

Process management is handled by **PM2** via the [ecosystem.config.js](file:///home/jackc/projects/homma-research/ecosystem.config.js) configuration:

### 1. Launching All Services
```bash
cd /opt/trading-journal
pm2 start ecosystem.config.js
```

This starts 5 decoupled services:
1. `fastapi-backend` (FastAPI web server running on port 5000)
2. `celery-worker` (Background task engine executing deep research modules)
3. `celery-beat` (Schedules daily gainer ingestion and nightly database cleanups)
4. `nextjs-frontend` (Next.js server running on port 3000)
5. `schwab-streamer` (WebSocket stream daemon piping ticker ticks into Redis)

### 2. PM2 Commands
- **Check Status**: `pm2 status`
- **View Logs**: `pm2 logs` or specific service logs: `pm2 logs fastapi-backend`
- **Restart All**: `pm2 restart ecosystem.config.js`
- **Stop All**: `pm2 stop ecosystem.config.js`

---

## 🗄️ TimescaleDB Time-Series Optimization

The database leverages TimescaleDB hypertables, retention policies, and continuous aggregates to process high-frequency ticks efficiently.

### 1. Hypertables & Compression
- **Hypertables**: `price_history_1min`, `options_snapshot`, `indicators`, and `screener_alerts` are chunked dynamically into 7-day intervals.
- **Compression**: Automatic compression runs on chunks older than **7 days** (segmentby = `symbol`), reducing disk footprint by up to 90%.
- **Retention Policies**:
  - `price_history_1min`: Automatically pruned after **90 days**.
  - `options_snapshot`: Automatically pruned after **30 days**.
  - `screener_alerts`: Automatically pruned after **365 days**.

### 2. Continuous Aggregates
- **`price_history_5min`**: Real-time 5-minute candles automatically rolled up in the background.
- **`price_history_15min`**: Real-time 15-minute candles automatically rolled up in the background.

---

## 📊 Historical Data Management

### Pull Raw Daily Gainers
```bash
source backend/venv/bin/activate
python3 scripts/pull_historical.py
```

### Enrich Historical Runs with Yahoo Finance Data
```bash
python3 scripts/enrich_historical.py --limit 500
```

---

## 📁 Project Structure

```
trading-journal/
├── backend/
│   ├── fastapi_app/
│   │   ├── db/           # OHLCV, indicator, and strategy database access layers
│   │   ├── routers/      # FastAPI endpoints (Gainers, Watchlist, Charts, etc.)
│   │   ├── tasks/        # Celery background task scripts
│   │   ├── celery_app.py # Celery app configuration
│   │   ├── scheduler.py  # APScheduler cron job manager
│   │   └── main.py       # FastAPI application entrypoint
│   ├── config.py         # Base configuration schemas
│   └── requirements.txt  # Python requirements
├── frontend/
│   ├── app/              # Next.js page components
│   ├── components/       # Custom React widgets & badges
│   └── lib/              # API interfaces and fetch hooks
├── momentum_screener/
│   └── schwab/
│       └── stream_client.py # Live Level 1 WebSocket Streamer
├── scripts/              # Auth utilities and historical backfills
├── docker-compose.yml    # Database + Redis configuration
└── ecosystem.config.js   # Production PM2 processes config
```
