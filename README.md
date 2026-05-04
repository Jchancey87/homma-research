# Trading Pattern Journal 📈

A sophisticated, self-hosted trade journal and research platform designed for technical traders focused on small-cap breakouts, gap-and-go trades, and momentum archetypes.

## 🚀 Overview

This platform automates the process of identifying, analyzing, and journaling market gainers. It combines high-performance interactive charting with a multi-module AI research engine that provides forensic-level analysis of any ticker on demand.

## 🛠️ Technology Stack

- **Backend**: Python 3.11, Flask (Modular Blueprints), SQLite (local, zero-config)
- **Frontend**: Next.js 14 (App Router), Tailwind CSS, [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- **AI/LLM**:
  - **Text**: Groq (Llama 3) for rapid structured analysis reports.
  - **Vision**: Gemini 1.5 Pro/Flash for automated chart annotation and pattern recognition.
- **Data Pipeline**: Polygon.io (Primary), yfinance (Fallback/Historical), SEC EDGAR (Free, no key required), finviz
- **Deployment**: PM2 (Process Management), Nginx Proxy Manager (Self-hosting)

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

## ⚙️ Setup & Installation

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- API Keys: Polygon.io, Groq, and Gemini.

### 2. Configuration
Copy the example environment file and fill in your credentials:
```bash
cp .env.example backend/.env
```

**Required variables:**

| Variable | Purpose |
|---|---|
| `POLYGON_API_KEY` | Market data (news, OHLCV, aggregates) |
| `LLM_API_KEY` | Groq API key for text analysis |
| `GEMINI_API_KEY` | Gemini vision API key for chart annotation |
| `SEC_USER_AGENT` | Your name + email (e.g. `John Doe john@email.com`) — required by SEC EDGAR (free) |
| `SMTP_*` | Email credentials for daily reports |

### 3. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## 📊 Historical Data Management

The system supports importing historical trade data from CSV files for backtesting and pattern analysis.

1. Ensure your CSV follows the schema: `Date, Ticker, Gap %, Float, RVOL, Sector, Market Cap, News, Close, Open`.
2. Run the ingestion script:
```bash
python scripts/import_historical.py /path/to/your_data.csv
```

## 📁 Project Structure

```
trading-journal/
├── backend/
│   ├── routes/         # Flask API blueprints (gainers, charts, analysis)
│   ├── services/       # Data gathering services
│   │   ├── sec_service.py          # SEC EDGAR (filings, EFTS search, XBRL)
│   │   ├── risk_service.py         # Risk Detection data pipeline
│   │   ├── catalyst_service.py     # Catalyst Analysis data pipeline
│   │   ├── context_service.py      # Deep Context data pipeline
│   │   └── ...
│   ├── llm/            # LLM clients (Groq text, Gemini vision)
│   ├── jobs/           # Cron automation (ingestion, daily email)
│   └── models/         # SQLite schema
├── frontend/
│   ├── app/            # Next.js pages
│   │   └── research/   # Deep Research tabbed interface
│   ├── components/
│   │   └── research/   # FeaturePanel and research-specific components
│   └── lib/            # API client (api.ts)
├── scripts/            # Data import and enrichment utilities
├── data/               # SQLite database
└── storage/            # Generated charts and screenshots
```

## 📖 Documentation

- **[Backend Architecture & API](backend/README.md)**
- **[Frontend & Charting Components](frontend/README.md)**
- **[Data Pipeline & Scripts](scripts/README.md)**
- **[Full System Architecture](docs/ARCHITECTURE.md)**

---
*Built for traders who value data-driven edge and automated workflows.*
