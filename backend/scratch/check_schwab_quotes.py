import sys
import os
import json

# Add backend and project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Load dotenv to get Schwab keys
from dotenv import load_dotenv
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

from momentum_screener.schwab.http_client import get_quotes

def main():
    # Let's fetch quotes for some common tickers
    tickers = ['SPY', 'QQQ', 'IWM']
    print(f"Fetching quotes for {tickers}...")
    res = get_quotes(tickers)
    print(json.dumps(res, indent=2))

if __name__ == '__main__':
    main()
