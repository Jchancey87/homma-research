#!/usr/bin/env python3
"""
Nightly 1-minute candle ingestion job.
Fetches daily 1-minute bars for all US equities with market cap <$10B.
Runs at market close (e.g. 8:30 PM ET).
"""
import sys
import os
import time
import argparse
import logging
from datetime import datetime, timedelta, date as date_cls
import pytz

# Add paths
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from config import Config
from database import get_connection
from momentum_screener.schwab.http_client import get_price_history_every_minute, get_instruments

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 50
RATE_LIMIT_DELAY = 0.6  # delay between Schwab API calls (~100 calls/min)

def fetch_and_seed_tickers():
    """
    Fetch all active US stock tickers from NASDAQ Trader directory
    and insert/update them in stock_fundamentals.
    """
    import requests
    log.info("Fetching US equity directory from NASDAQ Trader...")
    tickers = []
    
    # 1. Nasdaq Listed
    try:
        r = requests.get("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", timeout=15)
        if r.status_code == 200:
            lines = r.text.split('\n')
            for line in lines[1:]:
                parts = line.split('|')
                if len(parts) > 1:
                    symbol = parts[0].strip()
                    # Filter out test symbols and non-standard tickers
                    if symbol and symbol.isalpha() and parts[6].strip() == 'N':
                        tickers.append(symbol)
    except Exception as e:
        log.warning(f"Error fetching Nasdaq listed directory: {e}")
        
    # 2. Other Listed (NYSE, AMEX)
    try:
        r = requests.get("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", timeout=15)
        if r.status_code == 200:
            lines = r.text.split('\n')
            for line in lines[1:]:
                parts = line.split('|')
                if len(parts) > 1:
                    symbol = parts[0].strip()
                    if symbol and symbol.isalpha() and parts[7].strip() == 'N':
                        tickers.append(symbol)
    except Exception as e:
        log.warning(f"Error fetching Other listed directory: {e}")
        
    tickers = sorted(list(set(tickers)))
    log.info(f"Resolved {len(tickers)} active US tickers. Seeding database...")
    
    # Seed in DB with ON CONFLICT DO NOTHING
    with get_connection() as conn:
        cur = conn._conn.cursor()
        for i in range(0, len(tickers), 100):
            batch = tickers[i:i+100]
            values = [(s, 'Unknown') for s in batch]
            cur.executemany(
                "INSERT INTO stock_fundamentals (symbol, company_name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                values
            )
    log.info("Ticker seeding complete.")

def update_fundamentals_cache():
    """
    Refresh fundamentals for seeded tickers in batches of 50.
    Updates company_name, market_cap, shares_outstanding, PE ratio, etc.
    """
    log.info("Refreshing fundamentals cache from Schwab...")
    # Select tickers that haven't been updated in 7 days
    with get_connection() as conn:
        cur = conn._conn.cursor()
        cur.execute("""
            SELECT symbol FROM stock_fundamentals 
            WHERE updated_at IS NULL OR updated_at < NOW() - INTERVAL '7 days'
        """)
        tickers = [r['symbol'] for r in cur.fetchall()]
        
    if not tickers:
        log.info("All fundamentals are up to date.")
        return
        
    log.info(f"Updating fundamentals for {len(tickers)} symbols...")
    
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i+BATCH_SIZE]
        symbols_str = ",".join(batch)
        
        try:
            data = get_instruments(symbols_str)
            if not data:
                time.sleep(RATE_LIMIT_DELAY)
                continue
                
            with get_connection() as conn:
                cur = conn._conn.cursor()
                for sym in batch:
                    inst = data.get(sym)
                    if not inst or 'fundamental' not in inst:
                        continue
                    
                    fund = inst['fundamental']
                    co_name = inst.get('description', '')
                    mkt_cap = int(fund.get('marketCap', 0) * 1_000_000) # Schwab cap is in millions
                    shares_out = int(fund.get('sharesOutstanding', 0) * 1_000_000)
                    div_yield = fund.get('dividendYield', 0.0)
                    pe_ratio = fund.get('peRatio', 0.0)
                    pb_ratio = fund.get('pbRatio', 0.0)
                    beta = fund.get('beta', 0.0)
                    vol_1d = int(fund.get('vol1DayAverage', 0))
                    vol_10d = int(fund.get('vol10DayAverage', 0))
                    vol_3m = int(fund.get('vol3MonthAverage', 0))
                    high_52w = fund.get('high52Week', 0.0)
                    low_52w = fund.get('low52Week', 0.0)
                    
                    # Float categorization
                    float_cat = "Unknown"
                    if shares_out:
                        if shares_out <= 10_000_000: float_cat = "Micro-Float"
                        elif shares_out <= 20_000_000: float_cat = "Low-Float"
                        elif shares_out <= 50_000_000: float_cat = "Mid-Float"
                        else: float_cat = "High-Float"
                    
                    cur.execute("""
                        INSERT INTO stock_fundamentals (
                            symbol, company_name, shares_outstanding, market_cap,
                            pe_ratio, pb_ratio, dividend_yield, beta,
                            vol_1d_avg, vol_10d_avg, vol_3m_avg, high_52wk, low_52wk,
                            float_category, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                        ) ON CONFLICT (symbol) DO UPDATE SET
                            company_name = EXCLUDED.company_name,
                            shares_outstanding = EXCLUDED.shares_outstanding,
                            market_cap = EXCLUDED.market_cap,
                            pe_ratio = EXCLUDED.pe_ratio,
                            pb_ratio = EXCLUDED.pb_ratio,
                            dividend_yield = EXCLUDED.dividend_yield,
                            beta = EXCLUDED.beta,
                            vol_1d_avg = EXCLUDED.vol_1d_avg,
                            vol_10d_avg = EXCLUDED.vol_10d_avg,
                            vol_3m_avg = EXCLUDED.vol_3m_avg,
                            high_52wk = EXCLUDED.high_52wk,
                            low_52wk = EXCLUDED.low_52wk,
                            float_category = EXCLUDED.float_category,
                            updated_at = NOW()
                    """, (
                        sym, co_name, shares_out, mkt_cap,
                        pe_ratio, pb_ratio, div_yield, beta,
                        vol_1d, vol_10d, vol_3m, high_52w, low_52w,
                        float_cat
                    ))
            log.info(f"Updated fundamentals batch: {batch[0]}..{batch[-1]}")
        except Exception as e:
            log.error(f"Error updating fundamentals batch {batch}: {e}")
            
        time.sleep(RATE_LIMIT_DELAY)

def ingest_minute_candles(target_date: date_cls):
    """
    Ingest 1-minute candles for all tickers with market cap <$10B.
    """
    # 1. Resolve target symbols
    with get_connection() as conn:
        cur = conn._conn.cursor()
        cur.execute("""
            SELECT symbol FROM stock_fundamentals
            WHERE market_cap < 10000000000 AND vol_10d_avg > 10000
            ORDER BY vol_10d_avg DESC
        """)
        tickers = [r['symbol'] for r in cur.fetchall()]
        
    if not tickers:
        log.warning("No tickers found under $10B market cap with volume > 10k.")
        return
        
    log.info(f"Found {len(tickers)} tickers targeting for 1-minute candle ingestion.")
    
    # Establish date boundaries in Eastern time (Schwab API works with ET dates)
    tz_et = pytz.timezone('America/New_York')
    start_dt = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz_et)
    end_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=tz_et)
    
    # Convert to UTC or keep as ET for Schwab-py (schwab-py takes timezone aware datetimes)
    inserted_candles = 0
    
    for idx, sym in enumerate(tickers):
        try:
            candles = get_price_history_every_minute(sym, start_datetime=start_dt, end_datetime=end_dt)
            if not candles:
                time.sleep(RATE_LIMIT_DELAY)
                continue
                
            # Prepare rows
            rows = []
            for c in candles:
                ts_ms = c.get('datetime')
                if not ts_ms:
                    continue
                # Schwab returns milliseconds timestamp in UTC
                ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=pytz.UTC)
                
                rows.append((
                    sym,
                    ts,
                    c.get('open'),
                    c.get('high'),
                    c.get('low'),
                    c.get('close'),
                    c.get('volume')
                ))
                
            if rows:
                with get_connection() as conn:
                    cur = conn._conn.cursor()
                    cur.executemany("""
                        INSERT INTO price_history_1min (symbol, timestamp, open, high, low, close, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, timestamp) DO NOTHING
                    """, rows)
                inserted_candles += len(rows)
                
            if (idx + 1) % 50 == 0:
                log.info(f"Ingested {idx + 1}/{len(tickers)} tickers. Total candles inserted: {inserted_candles}")
                
        except Exception as e:
            log.error(f"Failed to ingest 1-minute candles for {sym}: {e}")
            
        time.sleep(RATE_LIMIT_DELAY)
        
    log.info(f"Ingestion complete for {target_date}. Total candles inserted: {inserted_candles}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Nightly 1-minute candle ingestion')
    parser.add_argument('--seed', action='store_true', help='Fetch ticker directory and seed fundamentals')
    parser.add_argument('--date', default=None, help='YYYY-MM-DD target date (defaults to today)')
    args = parser.parse_args()
    
    if args.seed:
        fetch_and_seed_tickers()
        update_fundamentals_cache()
    else:
        # Default to today
        target_date_str = args.date
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = datetime.now(pytz.timezone('US/Eastern')).date()
            
        log.info(f"Running candle ingestion for {target_date}...")
        ingest_minute_candles(target_date)
