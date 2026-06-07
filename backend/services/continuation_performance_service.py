"""
services/continuation_performance_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fetches historical daily bars and fundamental metrics to enrich
continuation picks and track their performance over Day 1, Day 2, and Day 3.
"""
import os
import logging
from datetime import datetime, date
import pytz
import asyncpg
from typing import Dict, Any, List, Optional

from database import get_connection
from services.schwab_client import get_daily_bars
from services.fmp_service import get_company_profile, get_cash_position, get_income_statement

log = logging.getLogger(__name__)

def update_all_continuation_performances() -> int:
    """
    Scans the continuation_picks table for recent picks (last 15 days)
    that are missing Day 3 performance, fetches daily history from Schwab/yfinance,
    and updates the database.
    
    Returns the number of updated picks.
    """
    query_picks = """
        SELECT id, ticker, date, close_d0, d1_close, d2_close, d3_close,
               market_cap, shares_outstanding, cash, runway_months, news_headline
        FROM continuation_picks
        WHERE date::date >= (CURRENT_DATE - INTERVAL '15 days')
          AND d3_close IS NULL
        ORDER BY date DESC
    """
    
    with get_connection() as conn:
        picks = conn.execute(query_picks).fetchall()
        if not picks:
            log.info("[performance_service] No continuation picks need updating.")
            return 0
            
        updated_count = 0
        for p in picks:
            pick_id = p['id']
            ticker = p['ticker']
            date_str = p['date']
            
            log.info(f"[performance_service] Updating continuation performance for {ticker} (date: {date_str})")
            
            # 1. Fetch fundamentals if they are missing
            fundamentals = {}
            if p['market_cap'] is None or p['cash'] is None or p['news_headline'] is None:
                fundamentals = _get_pick_fundamentals(conn, ticker, date_str)
                if fundamentals:
                    _update_pick_fundamentals_db(conn, pick_id, fundamentals)
            
            # 2. Fetch daily bars
            candles = _get_historical_candles(ticker)
            if not candles:
                log.warning(f"[performance_service] Could not fetch daily bars for {ticker}")
                continue
                
            # 3. Match Day 0, Day 1, Day 2, Day 3
            perf = _extract_daily_performance(candles, date_str)
            if perf:
                _update_pick_performance_db(conn, pick_id, perf)
                updated_count += 1
                
        return updated_count

def _get_pick_fundamentals(conn, ticker: str, date_str: str) -> Dict[str, Any]:
    """
    Attempts to fetch fundamental details from daily_gainers first.
    If not found, queries FMP / yfinance APIs.
    """
    # Try daily_gainers
    row = conn.execute(
        """SELECT market_cap, shares_outstanding, cash, net_income,
                  operating_cash_flow, runway_months, dilution_risk,
                  news_headline, news_fresh, sector
           FROM daily_gainers
           WHERE ticker = %s AND date = %s""",
        (ticker, date_str)
    ).fetchone()
    
    if row:
        log.info(f"[performance_service] Found fundamentals in daily_gainers for {ticker}")
        return dict(row)
        
    # If not found, fetch from APIs
    log.info(f"[performance_service] Fetching fresh API fundamentals for {ticker}")
    fundamentals = {
        'market_cap': None,
        'shares_outstanding': None,
        'cash': None,
        'net_income': None,
        'operating_cash_flow': None,
        'runway_months': None,
        'dilution_risk': 'Low',
        'news_headline': None,
        'news_fresh': False
    }
    
    try:
        profile = get_company_profile(ticker) or {}
        fundamentals['market_cap'] = profile.get('market_cap')
        fundamentals['shares_outstanding'] = profile.get('shares_outstanding')
    except Exception as e:
        log.warning(f"[performance_service] Profile fetch failed for {ticker}: {e}")
        
    try:
        cash_pos = get_cash_position(ticker) or {}
        fundamentals['cash'] = cash_pos.get('cash_and_cash_equivalents') or cash_pos.get('cash_and_short_term_investments')
        fundamentals['operating_cash_flow'] = cash_pos.get('operating_cash_flow') or cash_pos.get('net_cash_provided_by_operating_activities')
    except Exception as e:
        log.warning(f"[performance_service] Cash position fetch failed for {ticker}: {e}")
        
    try:
        inc_list = get_income_statement(ticker, quarters=1)
        if inc_list:
            fundamentals['net_income'] = inc_list[0].get('net_income') or inc_list[0].get('netIncome')
    except Exception as e:
        log.warning(f"[performance_service] Income statement fetch failed for {ticker}: {e}")
        
    # Heuristics
    cash_val = fundamentals['cash']
    ocf_val = fundamentals['operating_cash_flow']
    if cash_val is not None and ocf_val is not None and ocf_val < 0:
        monthly_burn = -ocf_val / 3.0
        if monthly_burn > 0:
            fundamentals['runway_months'] = round(cash_val / monthly_burn, 1)
            
    runway = fundamentals['runway_months']
    if runway is not None:
        if runway < 6:
            fundamentals['dilution_risk'] = 'High'
        elif runway < 12:
            fundamentals['dilution_risk'] = 'Medium'
        else:
            fundamentals['dilution_risk'] = 'Low'
            
    # News fallback
    try:
        from services.fmp_service import get_stock_news
        news = get_stock_news(ticker, limit=1)
        if news:
            fundamentals['news_headline'] = news[0].get('title')
            fundamentals['news_fresh'] = True
    except Exception as e:
        log.warning(f"[performance_service] News fetch failed for {ticker}: {e}")
        
    # YFinance Fallback
    if not fundamentals['market_cap']:
        try:
            import yfinance as yf
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info
            fundamentals['market_cap'] = info.get('marketCap')
            fundamentals['shares_outstanding'] = info.get('sharesOutstanding')
        except Exception as e:
            log.warning(f"[performance_service] YFinance fundamentals fallback failed for {ticker}: {e}")
            
    return fundamentals

def _get_historical_candles(ticker: str) -> List[Dict[str, Any]]:
    """Fetches daily candles for a ticker with yfinance fallback."""
    try:
        bars = get_daily_bars(ticker)
        if bars:
            return bars
    except Exception as e:
        log.warning(f"[performance_service] Schwab daily bars failed for {ticker}: {e}")
        
    # Fallback to YFinance
    try:
        import yfinance as yf
        import pandas as pd
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period="1mo")
        if not df.empty:
            candles = []
            for index, row in df.iterrows():
                ts_ms = int(index.timestamp() * 1000)
                candles.append({
                    'o': float(row['Open']),
                    'h': float(row['High']),
                    'l': float(row['Low']),
                    'c': float(row['Close']),
                    'v': float(row['Volume']),
                    't': ts_ms
                })
            return candles
    except Exception as e:
        log.warning(f"[performance_service] YFinance daily candles fallback failed for {ticker}: {e}")
        
    return []

def _extract_daily_performance(candles: List[Dict[str, Any]], date_str: str) -> Optional[Dict[str, Any]]:
    """
    Finds the candle matching date_str and extracts Day 0 close
    plus Day 1, Day 2, and Day 3 prices.
    """
    eastern = pytz.timezone('America/New_York')
    
    # 1. Match candle index for Day 0
    d0_idx = -1
    for i, c in enumerate(candles):
        ts = c['t']
        dt_utc = datetime.fromtimestamp(ts / 1000.0, tz=pytz.utc)
        dt_et = dt_utc.astimezone(eastern)
        candle_date = dt_et.strftime('%Y-%m-%d')
        
        if candle_date == date_str:
            d0_idx = i
            break
            
    if d0_idx == -1:
        log.warning(f"[performance_service] Could not find Day 0 candle for {date_str}")
        return None
        
    perf = {
        'close_d0': candles[d0_idx]['c'],
        'd1_open': None, 'd1_high': None, 'd1_low': None, 'd1_close': None, 'd1_volume': None,
        'd2_open': None, 'd2_high': None, 'd2_low': None, 'd2_close': None, 'd2_volume': None,
        'd3_open': None, 'd3_high': None, 'd3_low': None, 'd3_close': None, 'd3_volume': None
    }
    
    # Day 1
    if d0_idx + 1 < len(candles):
        c1 = candles[d0_idx + 1]
        perf['d1_open'] = c1['o']
        perf['d1_high'] = c1['h']
        perf['d1_low'] = c1['l']
        perf['d1_close'] = c1['c']
        perf['d1_volume'] = c1['v']
        
    # Day 2
    if d0_idx + 2 < len(candles):
        c2 = candles[d0_idx + 2]
        perf['d2_open'] = c2['o']
        perf['d2_high'] = c2['h']
        perf['d2_low'] = c2['l']
        perf['d2_close'] = c2['c']
        perf['d2_volume'] = c2['v']
        
    # Day 3
    if d0_idx + 3 < len(candles):
        c3 = candles[d0_idx + 3]
        perf['d3_open'] = c3['o']
        perf['d3_high'] = c3['h']
        perf['d3_low'] = c3['l']
        perf['d3_close'] = c3['c']
        perf['d3_volume'] = c3['v']
        
    return perf

def _update_pick_fundamentals_db(conn, pick_id: int, fund: Dict[str, Any]):
    """Saves fundamentals to the database."""
    conn.execute(
        """UPDATE continuation_picks
           SET market_cap = %s,
               shares_outstanding = %s,
               cash = %s,
               net_income = %s,
               operating_cash_flow = %s,
               runway_months = %s,
               dilution_risk = %s,
               news_headline = %s,
               news_fresh = %s
           WHERE id = %s""",
        (
            fund.get('market_cap'), fund.get('shares_outstanding'),
            fund.get('cash'), fund.get('net_income'),
            fund.get('operating_cash_flow'), fund.get('runway_months'),
            fund.get('dilution_risk'), fund.get('news_headline'),
            fund.get('news_fresh'), pick_id
        )
    )

def _update_pick_performance_db(conn, pick_id: int, perf: Dict[str, Any]):
    """Saves performance tracking prices to the database."""
    conn.execute(
        """UPDATE continuation_picks
           SET close_d0 = %s,
               d1_open = %s, d1_high = %s, d1_low = %s, d1_close = %s, d1_volume = %s,
               d2_open = %s, d2_high = %s, d2_low = %s, d2_close = %s, d2_volume = %s,
               d3_open = %s, d3_high = %s, d3_low = %s, d3_close = %s, d3_volume = %s
           WHERE id = %s""",
        (
            perf['close_d0'],
            perf['d1_open'], perf['d1_high'], perf['d1_low'], perf['d1_close'], perf['d1_volume'],
            perf['d2_open'], perf['d2_high'], perf['d2_low'], perf['d2_close'], perf['d2_volume'],
            perf['d3_open'], perf['d3_high'], perf['d3_low'], perf['d3_close'], perf['d3_volume'],
            pick_id
        )
    )
