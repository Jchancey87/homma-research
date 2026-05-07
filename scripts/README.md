# Utility Scripts 🛠️

This directory contains scripts for historical data management, enrichment, and maintenance.

## 📜 Available Scripts

### 1. `import_historical.py`
Imports raw CSV data into the PostgreSQL database.
- **Usage**: `python import_historical.py /path/to/data.csv`
- **Schema**: Expects columns for `Date, Ticker, Gap %, Float, RVOL, Sector, Market Cap, News, Close, Open`.

### 2. `enrich_historical.py`
Enriches the `daily_gainers` table with accurate metrics from yfinance.
- **Problem Solved**: Raw imports often have incorrect gap percentages (due to splits) and missing fundamental data (float, sector, market cap).
- **Features**:
  - Recalculates `gap_pct` using `(open - prev_close) / prev_close`.
  - Calculates `RVOL` based on a 20-day rolling average.
  - Fetches `float_shares`, `sector`, and `market_cap`.
  - Filters out suspect data (gaps > 2000% or < 10%).
- **Usage**: `python enrich_historical.py [--dry-run] [--ticker AAPL] [--limit 100]`

### 3. `pull_historical.py`
A utility to pull historical gainer lists from external sources or APIs (Polygon/HPG).

### 4. `import_historical.py`
Legacy/Utility script to import CSV-formatted historical gainer lists.

## ⚙️ Workflow for New Data

1. **Import**: Use `import_historical.py` to load your base CSV.
2. **Enrich**: Run `enrich_historical.py` to fill in missing metrics and validate gap data.
3. **Analyze**: The data is now ready for the frontend heatmap and archetype dashboards.
