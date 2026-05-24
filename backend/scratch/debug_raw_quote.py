import sys
import os
import dotenv
import pprint

# Load environment
dotenv.load_dotenv("/home/jackc/projects/homma-research/backend/.env")

sys.path.insert(0, "/home/jackc/projects/homma-research")
sys.path.insert(0, "/home/jackc/projects/homma-research/backend")

from momentum_screener.schwab.http_client import get_quotes

res = get_quotes(["PCLA"])
print("Raw Quote for PCLA:")
pprint.pprint(res)
