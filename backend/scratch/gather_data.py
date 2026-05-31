import os
import sys
import json
import datetime
import logging
import traceback

# Setup paths and environment
_backend = '/opt/trading-journal/backend'
sys.path.insert(0, _backend)
sys.path.insert(0, os.path.dirname(_backend))

import dotenv
dotenv.load_dotenv(os.path.join(_backend, '.env'))

import yfinance as yf
import pandas as pd
from momentum_screener.schwab.http_client import (
    get_http_client,
    get_instruments,
    get_quote,
    get_price_history_every_minute,
    get_price_history_every_day
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

tickers = ['SPRC', 'NCT', 'ATPC', 'SNOU', 'ASTC', 'IOTR', 'MASK', 'UMAC', 'RCAX', 'QTEX']
as_of_date = '2026-05-29'

def get_yfinance_fundamentals(ticker):
    data = {}
    try:
        t = yf.Ticker(ticker)
        # News
        news = t.news or []
        data['news'] = [{'title': n.get('title'), 'publisher': n.get('publisher'), 'link': n.get('link'), 'providerPublishTime': n.get('providerPublishTime')} for n in news]
        
        # Balance Sheet & Income Statement
        bs = t.quarterly_balance_sheet
        fin = t.quarterly_financials
        cf = t.quarterly_cashflow
        
        # Cash & Cash Equivalents
        # Look for multiple possible index names
        cash_keys = [
            'Cash Cash Equivalents And Short Term Investments',
            'Cash And Cash Equivalents',
            'Cash Financial',
            'Cash'
        ]
        cash_val = None
        if bs is not None and not bs.empty:
            for k in cash_keys:
                if k in bs.index:
                    val = bs.loc[k].dropna()
                    if not val.empty:
                        cash_val = float(val.iloc[0])
                        break
        data['cash'] = cash_val
        
        # Operating Cash Flow / Net Income
        net_income_val = None
        if fin is not None and not fin.empty:
            ni_keys = ['Net Income', 'Net Income Common Stockholders']
            for k in ni_keys:
                if k in fin.index:
                    val = fin.loc[k].dropna()
                    if not val.empty:
                        net_income_val = float(val.iloc[0])
                        break
        data['net_income'] = net_income_val

        ocf_val = None
        if cf is not None and not cf.empty:
            ocf_keys = ['Operating Cash Flow', 'Cash Flow From Operating Activities']
            for k in ocf_keys:
                if k in cf.index:
                    val = cf.loc[k].dropna()
                    if not val.empty:
                        ocf_val = float(val.iloc[0])
                        break
        data['operating_cash_flow'] = ocf_val

        # Shares outstanding history to check for dilution
        shares_history = {}
        if bs is not None and not bs.empty:
            for k in ['Ordinary Shares Number', 'Share Issued']:
                if k in bs.index:
                    row = bs.loc[k].dropna()
                    for date_idx, val in row.items():
                        date_str = str(date_idx).split()[0]
                        shares_history[date_str] = float(val)
                    break
        data['shares_history'] = shares_history
        
        # Calendar (earnings, etc.)
        cal = t.calendar
        if cal:
            data['calendar'] = str(cal)
        else:
            data['calendar'] = None
            
    except Exception as e:
        log.warning(f"Error fetching yfinance details for {ticker}: {e}")
        data['error'] = str(e)
    return data

def main():
    results = {}
    
    # Check date formats
    start_dt = datetime.datetime.strptime(as_of_date, '%Y-%m-%d')
    end_dt = start_dt + datetime.timedelta(days=1)
    
    for ticker in tickers:
        log.info(f"Processing {ticker}...")
        results[ticker] = {}
        
        # 1. Schwab instrument / fundamental
        try:
            ins = get_instruments(ticker)
            if ins and 'instruments' in ins and len(ins['instruments']) > 0:
                results[ticker]['schwab_fundamental'] = ins['instruments'][0].get('fundamental', {})
                results[ticker]['description'] = ins['instruments'][0].get('description', '')
                results[ticker]['exchange'] = ins['instruments'][0].get('exchange', '')
            else:
                results[ticker]['schwab_fundamental'] = {}
        except Exception as e:
            log.error(f"Error getting Schwab fundamentals for {ticker}: {e}")
            results[ticker]['schwab_fundamental_error'] = str(e)
            
        # 2. Schwab Quote
        try:
            q = get_quote(ticker)
            if q and ticker in q:
                results[ticker]['schwab_quote'] = q[ticker]
            else:
                results[ticker]['schwab_quote'] = {}
        except Exception as e:
            log.error(f"Error getting Schwab quote for {ticker}: {e}")
            results[ticker]['schwab_quote_error'] = str(e)
            
        # 3. Schwab Minute History
        try:
            min_candles = get_price_history_every_minute(ticker, start_datetime=start_dt, end_datetime=end_dt)
            results[ticker]['minute_candles'] = min_candles
            log.info(f"  Fetched {len(min_candles)} minute candles.")
        except Exception as e:
            log.error(f"Error getting minute history for {ticker}: {e}")
            results[ticker]['minute_candles_error'] = str(e)
            
        # 4. Schwab Daily History (60 sessions)
        try:
            daily_candles = get_price_history_every_day(ticker)
            # Filter or slice the last 60 sessions
            results[ticker]['daily_candles'] = daily_candles[-60:] if daily_candles else []
            log.info(f"  Fetched {len(results[ticker]['daily_candles'])} daily candles.")
        except Exception as e:
            log.error(f"Error getting daily history for {ticker}: {e}")
            results[ticker]['daily_candles_error'] = str(e)
            
        # 5. YFinance supplemental
        log.info(f"  Fetching yfinance details...")
        results[ticker]['yfinance'] = get_yfinance_fundamentals(ticker)
        
    # Write to a output file
    output_path = '/home/jackc/projects/homma-research/backend/scratch/recap_data_snapshot.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, default=str, indent=2)
    log.info(f"All data saved to {output_path}")

if __name__ == '__main__':
    main()
