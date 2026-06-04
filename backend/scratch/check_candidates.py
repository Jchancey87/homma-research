import asyncio
import asyncpg

async def main():
    dsn = "postgresql://journal:journal1@192.168.0.201:5432/trading_journal"
    conn = await asyncpg.connect(dsn)
    try:
        # Watchlist
        watchlist = await conn.fetch("SELECT * FROM watchlist")
        print(f"Watchlist tickers ({len(watchlist)}): {[r['ticker'] for r in watchlist]}")
        
        # Daily gainers
        daily_gainers = await conn.fetch("SELECT COUNT(*) FROM daily_gainers")
        print(f"Total rows in daily_gainers: {daily_gainers[0][0]}")
        
        # Daily gainers from today
        from datetime import datetime
        import pytz
        today_str = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
        today_gainers = await conn.fetch("SELECT * FROM daily_gainers WHERE date = $1", today_str)
        print(f"Daily gainers for today ({today_str}) ({len(today_gainers)}): {[r['ticker'] for r in today_gainers]}")
        
        # Stock fundamentals
        fundamentals_count = await conn.fetchval("SELECT COUNT(*) FROM stock_fundamentals")
        print(f"Total stock_fundamentals: {fundamentals_count}")
        
        # Select some fundamentals to see what is there
        high_vol_fund = await conn.fetch("""
            SELECT symbol, vol_10d_avg, market_cap FROM stock_fundamentals 
            WHERE vol_10d_avg > 500000 AND market_cap < 10000000000
            ORDER BY vol_10d_avg DESC LIMIT 10
        """)
        print("\nTop 10 candidates from stock_fundamentals:")
        for r in high_vol_fund:
            print(f"Symbol: {r['symbol']:<6} | Vol 10d Avg: {r['vol_10d_avg']:<10} | Market Cap: {r['market_cap']}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
