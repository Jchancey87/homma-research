# Trading Pattern Journal 📈

A sophisticated, self-hosted trade journal and research platform designed for technical traders focused on small-cap breakouts, gap-and-go trades, and momentum archetypes.

## 🚀 Overview

This platform automates the process of identifying, analyzing, and journaling market gainers. It combines high-performance interactive charting with a multi-module AI research engine that provides forensic-level analysis of any ticker on demand.

## 🛠️ Technology Stack

- **Backend**: Python 3.12, FastAPI (Asynchronous lifespan), PostgreSQL, Celery, Redis
- **Frontend**: Next.js 14 (App Router), Tailwind CSS, [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- **AI/LLM**:
  - **Text**: Groq (Llama 3) for rapid structured analysis reports.
  - **Vision**: Gemini 1.5 Pro/Flash for automated chart annotation and pattern recognition.
- **Data Pipeline**: Schwab Trader API (Market data & Level 1 WebSocket), Financial Modeling Prep (FMP - Primary Fundamental/Earnings), SEC EDGAR (Filings & PIPE detection), finviz, yfinance
- **Deployment**: Manual (Ubuntu/Proxmox LXC), Docker Compose (PostgreSQL & Redis), PM2 (Process Management), Nginx Proxy Manager

## ✨ Core Features

- **Morning Briefing Interface**:
  - **Tier 1 Intelligence**: Live market breadth (SPY/QQQ/IWM) with derived risk bias, auto-refreshing every 15 minutes.
  - **Repeat Runner Alerts**: Real-time cross-referencing of today's gainers against historical database appearances.
  - **Momentum Context**: Yesterday's follow-through tracker, float tier analysis (Nano/Micro/Small), and sector rotation trends.
  - **Watchlist Wake-Up**: Live Schwab pricing with "Flame" alerts for tickers moving >5%.
  - **Impeccable Design**: High-density, restrained aesthetic optimized for 4:00 AM dark-room analysis.
- **Command Center**:
  - **Unified Hub**: Combines real-time gainers, historical ticker tracking, and heatmaps into a single, filterable interface.
  - **Advanced Filtering**: Filter the entire history by Gap %, Float, RVOL, Sector, or specific date.
  - **Multi-View Heatmap**: Interactive "Float vs. RVOL" and "Avg Gap by Sector" visualizations to identify high-conviction momentum pockets.
- **Interactive Deep Research** (4 parallel analysis modules orchestrated out-of-thread via Celery):
  - **Full Report**: AI-generated analyst report with fundamental health, ownership, catalysts, and technical context.
  - **🚨 Risk Detection**: Scans SEC EDGAR for reverse splits, S-3 shelf registrations, 424B ATM offerings, toxic financing language, and short interest traps.
  - **⚡ Catalyst Analysis**: Event-date-aware rating — Tier 1 (binary), Tier 2 (soft), or Tier 3 (none) — with SEC 8-K item code parsing and FMP earnings integration.
  - **📊 Deep Context**: Produces a Setup Score (1–10) by combining SMA levels, RS vs SPY, float rotation, and historical appearance density.
- **Ticker History & Tracking**:
  - **Historical Lookup**: Searchable archive of every ticker that has ever appeared as a gainer.
  - **Repeat Appearance Tracking**: Automatically flags "repeat runners" with multi-period filtering (Week/Month/Year).
  - **Expanded Context**: Deep dive into every historical date a ticker ran — see its old news headlines, float, and catalyst freshness.
- **Asset Management**:
  - Local storage for trade screenshots with AI-assisted annotation and pattern tagging.
- **📋 Watchlist & Notes**: Quick-access tracking with bullish/bearish sentiment tagging and historical observation feeds.

## ⚙️ Setup & Installation (Manual — Proxmox/Ubuntu LXC)

This app runs manually on an Ubuntu LXC container on Proxmox with a shared PostgreSQL database.

### Infrastructure

| Component  | Address              | Notes                          |
|------------|----------------------|--------------------------------|
| App Server | `192.168.0.202`      | Ubuntu LXC — FastAPI + Next.js |
| Database & Redis | `192.168.0.201` | Proxmox — PostgreSQL + Redis   |
| Proxy      | Nginx Proxy Manager  | Separate LXC — handles routing |

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

### 3. Spin Up Infrastructure (PostgreSQL & Redis)
Ensure Docker Compose is installed on your database server, then run:
```bash
docker-compose up -d
```

### 4. Configure Environment
```bash
cp backend/.env.example backend/.env
nano backend/.env
```

**Required variables:**

| Variable | Purpose | Default / Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL DSN | `postgresql://journal:journal@192.168.0.201:5432/trading_journal` |
| `CELERY_BROKER_URL` | Redis broker connection | `redis://192.168.0.201:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis result store | `redis://192.168.0.201:6379/1` |
| `SCHWAB_API_KEY` | Schwab developer API key | `your_api_key` |
| `SCHWAB_API_SECRET` | Schwab developer API secret | `your_api_secret` |
| `FMP_API_KEY` | Financial Modeling Prep key | `your_fmp_key` |
| `LLM_API_KEY` | Groq API key for text reports | `your_groq_key` |
| `GEMINI_API_KEY` | Gemini API key for charts | `your_gemini_key` |
| `SEC_USER_AGENT` | User-agent for free SEC pulls | `Name email@domain.com` |

### 5. Backend Setup
```bash
cd /opt/trading-journal/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start the uvicorn server manually to test (FastAPI handles DB setup automatically on startup)
uvicorn fastapi_app.main:app --port 5000 --host 0.0.0.0
```

### 6. Frontend Setup
```bash
cd /opt/trading-journal/frontend
npx pnpm@9 install
export NEXT_PUBLIC_API_URL=https://homma-research.homma.casa
npx pnpm@9 run dev -- -H 0.0.0.0
```

### 7. Start Everything with Tmux (Recommended for Dev)
```bash
cd /opt/trading-journal
chmod +x start_journal.sh
./start_journal.sh
```

| Tmux Window | Purpose | Shortcut |
|---|---|---|
| `0: backend` | FastAPI server (Port 5000) | `Ctrl+b`, `0` |
| `1: frontend` | Next.js server (Port 3000) | `Ctrl+b`, `1` |
| `2: scripts` | Ingestion / Enrichment | `Ctrl+b`, `2` |
| `3: celery` | Celery Worker process | `Ctrl+b`, `3` |
| `4: streamer` | Schwab WebSocket Streamer Daemon | `Ctrl+b`, `4` |

**Detach** (keep running in background): `Ctrl+b`, then `d`  
**Re-attach**: `./start_journal.sh`

---

## 🗄️ TimescaleDB Optimization

The database is built on **TimescaleDB** (PostgreSQL 18 compatible) to support high-frequency market data ingestion.

### Hypertables & Compression
* **Hypertables**: `price_history_1min`, `options_snapshot`, and `screener_alerts` are structured as hypertables partitioned into **7-day chunks**.
* **Compression**: Automaterialized compression is configured for data older than **7 days** (segmentby = `symbol`), reducing disk footprints by ~90%.
* **Data Retention**:
  - `price_history_1min`: Automatically dropped after **90 days**.
  - `options_snapshot`: Automatically dropped after **30 days**.
  - `screener_alerts`: Automatically dropped after **365 days**.

### Continuous Aggregates (OHLCV)
* **`price_history_5min`**: Real-time 5-minute candles automatically rolled up from 1-minute data.
* **`price_history_15min`**: Real-time 15-minute candles automatically rolled up from 1-minute data.
* *Aggregates automatically update in the background every 5 and 15 minutes.*

---

## 📊 Historical Data Management

### Step 1: Pull the raw gainer list
```bash
source backend/venv/bin/activate
python3 scripts/pull_historical.py
```

### Step 2: Enrich with Yahoo Finance data
```bash
python3 scripts/enrich_historical.py --limit 500
```

---

## 🔒 Security

- This app is intended for **local network use only**.
- Do **not** forward ports 3000 or 5000 to the public internet.
- For remote access, use **[Tailscale](https://tailscale.com/)** — it creates a private encrypted tunnel and is free for personal use.

---

## 📁 Project Structure

```
trading-journal/
├── backend/
│   ├── fastapi_app/
│   │   ├── routers/      # FastAPI endpoints (Gainers, Watchlist, Charts, etc.)
│   │   ├── tasks/        # Celery background tasks
│   │   ├── celery_app.py # Celery app configuration
│   │   ├── db.py         # Asyncpg database connection pool
│   │   ├── scheduler.py  # APScheduler daily job manager
│   │   └── main.py       # FastAPI application entrypoint
│   ├── database.py       # Sync PG fallback connection for scripts
│   ├── config.py         # Shared base configuration
│   ├── requirements.txt  # Python requirements (no legacy Flask)
│   └── Dockerfile        # Production FastAPI image config
├── frontend/
│   ├── app/              # Next.js page components
│   └── components/       # Custom React widgets
├── scripts/              # Historical import / enrichment tools
├── docker-compose.yml    # Database + Cache configuration
├── ecosystem.config.js   # Production PM2 processes config
└── start_journal.sh      # Development TMUX launcher
```
