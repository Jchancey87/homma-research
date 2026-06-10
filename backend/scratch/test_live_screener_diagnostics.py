import sys
import os

# Set up paths
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
repo_root = os.path.dirname(backend_dir)
sys.path.insert(0, repo_root)
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, '.env'))

import logging
logging.basicConfig(level=logging.INFO)

from services.live_screener import get_live_gainers, refresh_cache
import pprint

print("Starting live screener check...")
try:
    # Force refresh the cache
    res = get_live_gainers(force=True)
    print("\nSUCCESS! Live gainers fetched:")
    print(f"Session: {res.get('session')} ({res.get('session_label')})")
    print(f"Fetched at: {res.get('fetched_at')}")
    print(f"Number of gainers: {len(res.get('gainers', []))}")
    print("Gainers tickers:")
    print([g['ticker'] for g in res.get('gainers', [])])
except Exception as e:
    print("\nFAILED with exception:")
    import traceback
    traceback.print_exc()
