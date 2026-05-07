#!/usr/bin/env python3
"""
Post-close gainer ingestion job.
Triggered by cron at 4:15 PM CT Mon–Fri:
  15 16 * * 1-5 /opt/trading-journal/venv/bin/python /opt/trading-journal/backend/jobs/ingest_gainers.py

Can also be run manually:
  python ingest_gainers.py --date 2026-05-01
  python ingest_gainers.py --dry-run
"""
import sys
import os
import argparse
import logging
from datetime import date as date_cls

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import yfinance as yf
import pandas as pd
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Screening criteria constants
# ---------------------------------------------------------------------------
MIN_GAP_PCT    = 10.0   # > 10% gap
MAX_FLOAT_M    = 50.0   # < 50M shares (wider net; filter further in UI)
MIN_RVOL       = 2.0    # > 2x RVOL (hard filter at ingest)
MAX_MARKET_CAP = 500e6  # < $500M


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main():
    # Ensure target_date is based on New York time (US/Eastern)
    # This prevents UTC servers from tagging late-night ingests as 'tomorrow'
    from datetime import datetime
    import pytz
    eastern = pytz.timezone('US/Eastern')
    ny_now  = datetime.now(eastern)
    
    parser = argparse.ArgumentParser(description='Ingest daily top gainers')
    parser.add_argument('--date',    default=ny_now.strftime('%Y-%m-%d'), help='YYYY-MM-DD')
    parser.add_argument('--dry-run', action='store_true', help='Fetch data but do not write to DB')
    args = parser.parse_args()

    target_date = args.date
    dry_run     = args.dry_run

    log.info(f"Starting ingestion for {target_date} (NY Time: {ny_now.strftime('%Y-%m-%d %H:%M:%S %Z')})")

    gainers = fetch_gainers(target_date)
    log.info(f"Found {len(gainers)} qualified gainers")

    if not gainers:
        log.warning("No gainers met criteria — exiting")
        return

    if dry_run:
        for g in gainers:
            log.info(f"  DRY RUN: {g}")
        return

    inserted, skipped = write_gainers(gainers, target_date)
    log.info(f"Done — inserted={inserted}, skipped (duplicate)={skipped}")


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_gainers(target_date: str) -> list[dict]:
    """
    Pull top small-cap gainers using Polygon (if key provided), then finviz, 
    then fallback to yfinance.
    """
    tickers = []
    
    if Config.POLYGON_API_KEY:
        tickers = _get_tickers_from_polygon()
        if tickers:
            log.info(f"Polygon returned {len(tickers)} tickers")
        else:
            log.warning("Polygon returned no tickers — trying finviz")
            
    if not tickers:
        tickers = _get_tickers_from_finviz()
        
    if not tickers:
        log.warning("finviz returned no tickers — trying yfinance trending")
        tickers = _get_tickers_fallback()

    # Also grab specifically after-hours movers to ensure continuation accuracy
    ah_tickers = _get_tickers_after_hours()
    if ah_tickers:
        log.info(f"Added {len(ah_tickers)} post-market movers")
        tickers = list(set(tickers + ah_tickers))

    if not tickers:
        log.error("No tickers found from any source")
        return []

    return _enrich_with_yfinance(tickers, target_date)


def _get_tickers_from_polygon() -> list[str]:
    """Fetch top gainers from Polygon Snapshot API."""
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={Config.POLYGON_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        tickers = [s['ticker'] for s in data.get('tickers', []) if s.get('ticker')]
        return tickers[:50]
    except Exception as e:
        log.warning(f"Polygon API failed: {e}")
        return []


def _get_tickers_from_finviz() -> list[str]:
    """Use finviz screener to get small-cap gappers."""
    try:
        from finviz.screener import Screener
        # Filters: US equities, gap > 5%, float < 50M, price > $1
        filters = [
            'geo_usa',
            'ta_gap_u5',       # gap up > 5%
            'sh_float_u50',    # float under 50M
            'sh_price_o1',     # price over $1
        ]
        stocks = Screener(filters=filters, table='Overview', order='-change')
        tickers = [s['Ticker'] for s in stocks if s.get('Ticker')]
        log.info(f"finviz returned {len(tickers)} tickers")
        return tickers[:30]  # cap to top 30
    except Exception as e:
        log.warning(f"finviz screener failed: {e}")
        return []


def _get_tickers_fallback() -> list[str]:
    """Fallback: pull from Yahoo Finance trending/most-active."""
    try:
        import requests
        # Yahoo Finance most-active small-cap (unofficial endpoint)
        url = (
            "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
            "?formatted=false&scrIds=day_gainers&count=25"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        quotes = resp.json()['finance']['result'][0]['quotes']
        return [q['symbol'] for q in quotes if q.get('symbol')]
    except Exception as e:
        log.warning(f"Yahoo fallback failed: {e}")
        return []
def _get_tickers_after_hours() -> list[str]:
    """Specifically fetch movers from Yahoo's After Hours gainer list."""
    try:
        url = (
            "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
            "?formatted=false&scrIds=after_hours_gainers&count=25"
        )
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        quotes = resp.json()['finance']['result'][0]['quotes']
        return [q['symbol'] for q in quotes if q.get('symbol')]
    except Exception as e:
        log.warning(f"After-hours fetch failed: {e}")
        return []


def _enrich_with_yfinance(tickers: list[str], target_date: str) -> list[dict]:
    """Download OHLCV + info for each ticker and build gainer rows."""
    gainers = []

    for ticker in tickers:
        try:
            t    = yf.Ticker(ticker)
            info = t.info or {}

            # Price data — use 2-day window to compute gap
            hist = t.history(period='2d', interval='1d')
            if len(hist) < 1:
                continue

            today_row = hist.iloc[-1]
            prev_row  = hist.iloc[-2] if len(hist) >= 2 else None

            # Get the "True" current price (prefer post-market if available)
            prev_close = info.get('regularMarketPreviousClose') or (float(prev_row['Close']) if prev_row is not None else None)
            
            # Use post-market price if it's currently after hours
            current_price = info.get('postMarketPrice') or info.get('currentPrice') or float(today_row['Close'])
            
            if prev_close:
                gap_pct = ((current_price - prev_close) / prev_close) * 100
            else:
                gap_pct = 0

            if gap_pct < MIN_GAP_PCT:
                continue

            float_shares = info.get('floatShares')
            market_cap   = info.get('marketCap')
            sector       = info.get('sector') or info.get('industry')

            if float_shares and float_shares > MAX_FLOAT_M * 1e6:
                continue
            if market_cap and market_cap > MAX_MARKET_CAP:
                continue

            # RVOL: volume today / avg volume
            volume     = float(today_row.get('Volume', 0))
            avg_volume = float(info.get('averageVolume', 0) or info.get('averageDailyVolume10Day', 0) or 1)
            rvol_15m   = round(volume / avg_volume, 2) if avg_volume else None

            if rvol_15m is not None and rvol_15m < MIN_RVOL:
                continue

            news_headline = _get_news_headline(t)
            news_fresh    = _classify_news(news_headline)

            gainers.append({
                'ticker':        ticker,
                'gap_pct':       round(gap_pct, 2),
                'float_shares':  float_shares,
                'rvol_15m':      rvol_15m,
                'sector':        sector,
                'market_cap':    market_cap,
                'news_headline': news_headline,
                'news_fresh':    news_fresh,
                'close_price':   round(current_price, 4),
                'open_price':    round(float(today_row['Open']), 4),
            })

        except Exception as e:
            log.warning(f"Failed to enrich {ticker}: {e}")
            continue

    return gainers


def _get_news_headline(ticker_obj) -> str | None:
    """Return the most recent news headline for the ticker."""
    try:
        news = ticker_obj.news
        if news:
            return news[0].get('title')
    except Exception:
        pass
    return None


def _classify_news(headline: str | None) -> bool:
    """Call LLM to classify news freshness. Returns False if LLM unavailable."""
    if not headline:
        return False
    try:
        from llm.llm_client import classify_news_fresh
        return classify_news_fresh(headline)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Database write
# ---------------------------------------------------------------------------

def write_gainers(gainers: list[dict], target_date: str) -> tuple[int, int]:
    from database import get_connection

    inserted = 0
    skipped  = 0

    with get_connection() as conn:
        for g in gainers:
            try:
                conn.execute(
                    """INSERT INTO daily_gainers
                       (date, ticker, gap_pct, float_shares, rvol_15m, sector,
                        market_cap, news_headline, news_fresh, close_price, open_price)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        target_date,
                        g['ticker'],
                        g['gap_pct'],
                        g['float_shares'],
                        g['rvol_15m'],
                        g['sector'],
                        g['market_cap'],
                        g['news_headline'],
                        g['news_fresh'],
                        g['close_price'],
                        g['open_price'],
                    ),
                )
                inserted += 1
            except Exception as e:
                if 'unique' in str(e).lower():
                    skipped += 1
                else:
                    log.error(f"DB error for {g['ticker']}: {e}")

    return inserted, skipped


if __name__ == '__main__':
    main()
