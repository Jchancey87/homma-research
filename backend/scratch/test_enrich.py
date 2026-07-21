"""
Spot-check _fetch_single_ticker_metrics for a real ticker to verify data quality.
"""
import sys, os
sys.path.insert(0, "/opt/trading-journal/backend")
sys.path.insert(0, "/opt/trading-journal")

from dotenv import load_dotenv
load_dotenv("/opt/trading-journal/backend/.env")

from services.watchlist_service import _fetch_single_ticker_metrics

ticker = "SANA"   # Small-cap biotech on watchlist
result = _fetch_single_ticker_metrics(ticker, None, None)
print(f"Ticker: {ticker}")
print(f"  runway_months: {result['runway_months']}")
print(f"  dilution:      {result['dilution']}")
print(f"  catalyst:      {result['upcoming_catalyst']}")
print(f"  catalyst_date: {result['catalyst_date']}")
