import sys
import os

# Add backend and parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config import Config
from momentum_screener.schwab.http_client import get_instruments

def main():
    symbol = "TSLA"
    print(f"Fetching instruments for: {symbol}")
    data = get_instruments(symbol)
    print("\nAPI Response:")
    import pprint
    pprint.pprint(data)

if __name__ == "__main__":
    main()
