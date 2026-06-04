import sys
import os
import asyncio

# Add backend and parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from momentum_screener.schwab.stream_client import SchwabStreamer

async def test_streamer():
    print("--- Testing SchwabStreamer Candidate Ingestion and Seeding ---")
    streamer = SchwabStreamer()
    await streamer.init_db()
    
    # Get candidates
    print("\nFetching candidate symbols...")
    candidates = await streamer.get_candidate_symbols()
    print(f"Candidates returned ({len(candidates)}): {sorted(list(candidates))}")
    
    # Load fundamentals (should fetch any missing from Schwab and insert into DB)
    print("\nLoading fundamentals (fetching missing ones from Schwab)...")
    await streamer.load_fundamentals(candidates)
    
    # Check if fundamentals are cached
    print("\nCached fundamentals check:")
    for sym in sorted(list(candidates)):
        cached = streamer.fundamentals_cache.get(sym)
        if cached:
            print(f"  {sym:<6} | Float: {cached['shares_outstanding']/1e6:>7.2f}M | 10d Avg Vol: {cached['vol_10d_avg']:>10} | Float Cat: {cached['float_category']}")
        else:
            print(f"  {sym:<6} | MISSING!")
            
    await streamer.db_pool.close()
    print("\n--- Test Complete ---")

if __name__ == "__main__":
    asyncio.run(test_streamer())
