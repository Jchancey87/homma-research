import sys
import os
import json

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(_REPO_ROOT, 'backend', '.env'))

from momentum_screener.schwab.http_client import get_quotes

def main():
    tickers = ["EDBL", "IOTR", "BATL", "DCX", "BABX", "TC", "EOSER", "VEEE", "SKYQ", "LUCY", "SNDQ", "MUZ", "BABA", "YINN", "SOXS", "IONZ"]
    print(f"Fetching Schwab quotes for {len(tickers)} tickers...")
    res = get_quotes(tickers)
    for t in tickers:
        q = res.get(t, {})
        quote = q.get('quote', {})
        last_price = quote.get('lastPrice', 0)
        net_pct_change = quote.get('netPercentChange', 0) * 100
        vol = quote.get('totalVolume', 0)
        print(f"Ticker: {t:<6} | Last Price: {last_price:<7} | Change %: {net_pct_change:<7.2f} | Volume: {vol}")

if __name__ == '__main__':
    main()
