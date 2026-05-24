import sys
import os
import dotenv

# Load environment
dotenv.load_dotenv("/home/jackc/projects/homma-research/backend/.env")

# Add paths
sys.path.insert(0, "/home/jackc/projects/homma-research")
sys.path.insert(0, "/home/jackc/projects/homma-research/backend")

from services import schwab_client
from services.live_screener import _enrich_snapshot_tickers

def test_hybrid():
    print("Fetching gainer snapshot from schwab_client...")
    raw_tickers = schwab_client.get_gainers_snapshot(include_otc=False)
    print(f"Total raw tickers returned: {len(raw_tickers)}")
    
    if not raw_tickers:
        print("No tickers found. Exiting.")
        return
        
    print(f"First raw ticker sample: {raw_tickers[0]}")
    
    import services.live_screener as ls
    
    # Run through the live screener enrichment logic
    enriched = _enrich_snapshot_tickers(raw_tickers)
    print(f"\nTotal enriched gainers: {len(enriched)}")
    
    user_tickers = ['PCLA', 'AKTX', 'QBTX', 'ATPC', 'RGTX', 'NCPL', 'EDHL', 'AKAN', 'RYOJ', 'CODX']
    found_in_enriched = []
    
    print("\nTop 25 Enriched Gainers (surfaced in Live Dashboard):")
    for idx, e in enumerate(enriched[:25]):
        ticker = e['ticker']
        float_m = f"{e['float_shares'] / 1e6:.2f}M" if e['float_shares'] else "—"
        mcap_m = f"{e['market_cap'] / 1e6:.2f}M" if e['market_cap'] else "—"
        print(f"  {idx+1:02d}. {ticker:6s}: Price: {e['last_price']:8.4f}, Change: {e['gap_pct']:6.2f}%, Volume: {e['volume']:12,}, Float: {float_m:8s}, Market Cap: {mcap_m:10s}, Sector: {e['sector']}")
        if ticker in user_tickers:
            found_in_enriched.append(ticker)
            
    print(f"\nChecking our final enriched list against the user's screen list:")
    print(f"Found {len(found_in_enriched)} of {len(user_tickers)} user tickers in enriched list: {found_in_enriched}")
    missing = [t for t in user_tickers if t not in [e['ticker'] for e in enriched]]
    print(f"Missing tickers: {missing}")

if __name__ == '__main__':
    test_hybrid()
