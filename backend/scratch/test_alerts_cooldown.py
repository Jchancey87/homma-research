import asyncio
import os
import asyncpg
from datetime import datetime, timedelta

DATABASE_URL = "postgresql://journal:journal1@192.168.0.201:5432/trading_journal?sslmode=disable"

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    print("Connected to DB.")

    try:
        # Clear cooldowns table for a clean test
        await conn.execute("TRUNCATE alerts.ticker_cooldowns CASCADE;")
        print("Truncated ticker_cooldowns.")

        # Test 1: Fire a new alert for 'AAPL' at $150.00
        # Signature: alerts.should_fire_alert(p_ticker, p_price, p_cooldown_interval, p_macro_window, p_macro_threshold)
        # We will use 1 minute cooldown, 10s macro window, 5 macro threshold.
        res1 = await conn.fetchval(
            "SELECT alerts.should_fire_alert($1, $2, $3, $4, $5)",
            "AAPL", 150.0, timedelta(minutes=1), timedelta(seconds=10), 5
        )
        print(f"Test 1 (New symbol AAPL @ 150.0): expected True, got {res1}")

        # Test 2: Fire AAPL alert again at lower or equal price ($150.00) during cooldown
        res2 = await conn.fetchval(
            "SELECT alerts.should_fire_alert($1, $2, $3, $4, $5)",
            "AAPL", 150.0, timedelta(minutes=1), timedelta(seconds=10), 5
        )
        print(f"Test 2 (AAPL @ 150.0 again - cooldown active): expected False, got {res2}")

        # Test 3: Fire AAPL alert at a higher price ($155.00) during cooldown (New Higher High Breakout)
        res3 = await conn.fetchval(
            "SELECT alerts.should_fire_alert($1, $2, $3, $4, $5)",
            "AAPL", 155.0, timedelta(minutes=1), timedelta(seconds=10), 5
        )
        print(f"Test 3 (AAPL @ 155.0 - breakout during cooldown): expected True, got {res3}")

        # Test 4: Fire AAPL alert at a lower price ($153.00) during cooldown
        res4 = await conn.fetchval(
            "SELECT alerts.should_fire_alert($1, $2, $3, $4, $5)",
            "AAPL", 153.0, timedelta(minutes=1), timedelta(seconds=10), 5
        )
        print(f"Test 4 (AAPL @ 153.0 - below highest price 155): expected False, got {res4}")

        # Test 5: Test Macro Market Throttle
        # Let's insert 5 distinct symbol alerts into screener_alerts in the last 1 second to trigger macro throttle
        # Since screener_alerts uses the alert_time column
        print("Inserting mock screener_alerts to trigger macro throttle...")
        symbols = ["MSFT", "GOOG", "TSLA", "AMZN", "NFLX"]
        for sym in symbols:
            await conn.execute(
                "INSERT INTO public.screener_alerts (symbol, alert_time, trigger_price, trigger_volume, rel_vol, gap_pct, float_shares, alert_type, sent) "
                "VALUES ($1, NOW(), 100.0, 1000, 2.0, 0.0, 10000000, 'TEST_ALERT', FALSE)",
                sym
            )

        # Now test should_fire_alert for AAPL (which should be blocked by macro throttle)
        res5 = await conn.fetchval(
            "SELECT alerts.should_fire_alert($1, $2, $3, $4, $5)",
            "AAPL", 160.0, timedelta(minutes=1), timedelta(seconds=10), 5
        )
        print(f"Test 5 (AAPL @ 160.0 - blocked by macro throttle): expected False, got {res5}")

    finally:
        # Cleanup
        await conn.execute("DELETE FROM public.screener_alerts WHERE alert_type = 'TEST_ALERT';")
        await conn.execute("TRUNCATE alerts.ticker_cooldowns CASCADE;")
        await conn.close()
        print("Disconnected and cleaned up.")

if __name__ == "__main__":
    asyncio.run(main())
