import sys
import os
import dotenv

# Load environment first!
dotenv.load_dotenv("/home/jackc/projects/homma-research/backend/.env")

sys.path.insert(0, "/home/jackc/projects/homma-research")
sys.path.insert(0, "/home/jackc/projects/homma-research/backend")

from services import schwab_client
from services.live_screener import _enrich_snapshot_tickers

raw_snaps = schwab_client.get_gainers_snapshot()
print(f"Fetched {len(raw_snaps)} raw snaps.")

pcla_snap = None
for s in raw_snaps:
    if s['ticker'] == 'PCLA':
        pcla_snap = s
        break

if pcla_snap:
    print("Found PCLA raw snapshot:")
    import pprint
    pprint.pprint(pcla_snap)
    
    # Try to enrich it
    enriched = _enrich_snapshot_tickers([pcla_snap])
    print("Enriched result for PCLA:")
    pprint.pprint(enriched)
else:
    print("PCLA NOT found in raw snaps! Here are all tickers in raw snaps:")
    print([s['ticker'] for s in raw_snaps])
