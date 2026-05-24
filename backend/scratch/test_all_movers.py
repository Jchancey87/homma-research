import sys
import os
import dotenv

# Load environment
dotenv.load_dotenv("/home/jackc/projects/homma-research/backend/.env")

# Add paths
sys.path.insert(0, "/home/jackc/projects/homma-research")
sys.path.insert(0, "/home/jackc/projects/homma-research/backend")

from momentum_screener.schwab.http_client import get_movers
from schwab.client import Client

indices = ['$COMPX', '$SPX', '$DJI', 'NASDAQ', 'NYSE', 'OTCBB', 'EQUITY_ALL', 'INDEX_ALL']
sorts = [
    Client.Movers.SortOrder.PERCENT_CHANGE_UP,
    Client.Movers.SortOrder.VOLUME
]

unique_symbols = set()

for index in indices:
    for sort in sorts:
        try:
            movers = get_movers(index, sort=sort)
            print(f"Index: {index}, Sort: {sort} -> Fetched {len(movers)} tickers")
            for m in movers:
                sym = m.get('symbol')
                if sym:
                    unique_symbols.add(sym)
                    # Print high changes or interesting tickers
                    chg = m.get('change')
                    pct = m.get('percentChange')
                    if pct and abs(pct) > 5:
                        print(f"  {sym}: {pct}%")
        except Exception as e:
            print(f"Failed index {index} sort {sort}: {e}")

print(f"\nTotal unique symbols fetched: {len(unique_symbols)}")
print(f"Unique symbols: {sorted(list(unique_symbols))}")
