# Trading Pattern Journal 📈

A sophisticated, self-hosted trade journal and research platform designed for technical traders focused on small-cap breakouts, gap-and-go trades, and momentum archetypes.

## 🚀 Overview

This platform automates the process of identifying, analyzing, and journaling market gainers. It combines high-performance interactive charting with a multi-module AI research engine that provides forensic-level analysis of any ticker on demand.

## 🛠️ Technology Stack

- **Backend**: Python 3.11, Flask (Modular Blueprints), PostgreSQL
- **Frontend**: Next.js 14 (App Router), Tailwind CSS, [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- **AI/LLM**:
  - **Text**: Groq (Llama 3) for rapid structured analysis reports.
  - **Vision**: Gemini 1.5 Pro/Flash for automated chart annotation and pattern recognition.
- **Data Pipeline**: Polygon.io (Primary), yfinance (Fallback/Historical), SEC EDGAR (Free, no key required), finviz
- **Deployment**: Manual (Ubuntu/Proxmox LXC), PM2 (Process Management), Nginx Proxy Manager

## ✨ Core Features

- **Daily Market Intelligence**:
  - Automated ingestion of top 100+ gainers at market close.
  - **Today's Overview**: A "morning briefing" dashboard showing top movers, active watchlists, and recent observations.
  - **Daily Chart Grid**: A high-performance, lazy-loaded responsive grid of the top 10 gainers for any date, featuring interactive candles + EMA 21.
- **Ticker History & Tracking**:
  - **Historical Lookup**: Searchable archive of every ticker that has ever appeared as a gainer.
  - **Repeat Appearance Tracking**: Automatically flags "repeat runners" with multi-period filtering (Week/Month/Year).
  - **Expanded Context**: Deep dive into every historical date a ticker ran — see its old news headlines, float, and catalyst freshness.
- **Interactive Deep Research** (4 parallel analysis modules):
  - **Full Report**: AI-generated analyst report with fundamental health, ownership, catalysts, and technical context.
  - **🚨 Risk Detection**: Scans SEC EDGAR for reverse splits, S-3 shelf registrations, 424B ATM offerings, toxic financing language, and short interest traps.
  - **⚡ Catalyst Analysis**: Event-date-aware rating — Tier 1 (binary), Tier 2 (soft), or Tier 3 (none) — with SEC 8-K item code parsing and full-text keyword search.
  - **📊 Deep Context**: Produces a Setup Score (1–10) by combining SMA levels, RS vs SPY, float rotation, and historical appearance density.
- **Visual Analytics & Heatmaps**:
  - **Multi-View Heatmap**: Interactive "Float vs. RVOL" and "Avg Gap by Sector" visualizations to identify high-conviction momentum pockets.
  - **Period Filtering**: Heatmaps automatically update based on the selected historical period (Week/Month/Year/All Time).
- **Asset Management**:
  - Local storage for trade screenshots with AI-assisted annotation and pattern tagging.
- **📋 Watchlist & Notes**: Quick-access tracking with bullish/bearish sentiment tagging and historical observation feeds.

## ⚙️ Setup & Installation (Manual — Proxmox/Ubuntu LXC)

This app runs manually on an Ubuntu LXC container on Proxmox with a shared PostgreSQL database.

### Infrastructure

| Component  | Address              | Notes                          |
|------------|----------------------|--------------------------------|
| App Server | `192.168.0.202`      | Ubuntu LXC — Flask + Next.js   |
| Database   | `192.168.0.201:5432` | Proxmox — PostgreSQL instance  |
| Proxy      | Nginx Proxy Manager  | Separate LXC — handles routing |

### 1. Prerequisites (Ubuntu LXC)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv nodejs npm git -y
```

### 2. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/Analysis-App.git /opt/trading-journal
cd /opt/trading-journal
```

### 3. Configure Environment
```bash
cp backend/.env.example backend/.env
nano backend/.env
```

**Required variables:**

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL DSN: `postgresql://user:pass@host:5432/trading_journal` |
| `POLYGON_API_KEY` | Market data (news, OHLCV, aggregates) |
| `LLM_API_KEY` | Groq API key for text analysis |
| `GEMINI_API_KEY` | Gemini vision API key for chart annotation |
| `SEC_USER_AGENT` | Your name + email (e.g. `John Doe john@email.com`) — required by SEC EDGAR (free) |
| `SMTP_*` | Email credentials for daily reports |

### 4. PostgreSQL Setup
```bash
# On your PostgreSQL server
sudo -u postgres psql
CREATE DATABASE trading_journal;
CREATE USER journal WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE trading_journal TO journal;
\c trading_journal
GRANT ALL ON SCHEMA public TO journal;
\q
```

### 5. Backend Setup
```bash
cd /opt/trading-journal/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Schema is created automatically on first run
python3 app.py
```

### 6. Frontend Setup
```bash
cd /opt/trading-journal/frontend
npm install
export NEXT_PUBLIC_API_URL=http://192.168.0.202:5000
npm run dev -- -H 0.0.0.0
```

### 7. Start Everything with Tmux (Recommended)
```bash
cd /opt/trading-journal
chmod +x start_journal.sh
./start_journal.sh
```

| Tmux Window | Purpose | Shortcut |
|---|---|---|
| `0: backend` | Flask API | `Ctrl+b`, `0` |
| `1: frontend` | Next.js UI | `Ctrl+b`, `1` |
| `2: scripts` | Ingestion / Enrichment | `Ctrl+b`, `2` |

**Detach** (keep running in background): `Ctrl+b`, then `d`
**Re-attach**: `./start_journal.sh`

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

> **Note**: Yahoo Finance is rate-limited. Use `--limit 50` for quick tests, `--limit 500+` for full history. Delisted tickers are automatically removed.

## 🔒 Security

- This app is intended for **local network use only**.
- Do **not** forward ports 3000 or 5000 to the public internet.
- For remote access, use **[Tailscale](https://tailscale.com/)** — it creates a private encrypted tunnel and is free for personal use.
- For pretty local URLs (e.g. `http://trading.local`), use **Nginx Proxy Manager** on a separate LXC.

## 📁 Project Structure

```
trading-journal/
├── backend/
│   ├── routes/         # Flask API blueprints
│   ├── services/       # Data gathering services
│   ├── llm/            # LLM clients
│   ├── jobs/           # Cron automation
│   └── models/         # PostgreSQL schema
├── frontend/
│   ├── app/            # Next.js pages
│   ├── components/     # UI components
│   └── lib/            # API client
├── scripts/            # Data import & enrichment utilities
├── storage/            # Screenshots & chart images
├── start_journal.sh    # Tmux startup script
└── ecosystem.config.js # PM2 config (production process manager)
```

## 📖 Documentation

- **[Backend Architecture & API](backend/README.md)**
- **[Frontend & Charting Components](frontend/README.md)**
- **[Data Pipeline & Scripts](scripts/README.md)**

---
*Built for traders who value data-driven edge and automated workflows.*
