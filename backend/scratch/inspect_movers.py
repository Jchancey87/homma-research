import sys
import os
import dotenv

# Load environment
dotenv.load_dotenv("/home/jackc/projects/homma-research/backend/.env")

# Add paths
sys.path.insert(0, "/home/jackc/projects/homma-research")
sys.path.insert(0, "/home/jackc/projects/homma-research/backend")

from momentum_screener.schwab.http_client import get_movers

movers = get_movers('EQUITY_ALL')
if movers:
    print("Mover structure:")
    import pprint
    pprint.pprint(movers[0])
else:
    print("No movers returned for EQUITY_ALL")
