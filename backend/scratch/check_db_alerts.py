import asyncio
import asyncpg
from datetime import datetime

async def main():
    dsn = "postgresql://journal:journal1@192.168.0.201:5432/trading_journal"
    print(f"Connecting to database: {dsn}")
    conn = await asyncpg.connect(dsn)
    try:
        # Check total number of alerts in screener_alerts
        count = await conn.fetchval("SELECT COUNT(*) FROM screener_alerts")
        print(f"Total alerts in database: {count}")
        
        # Check today's alerts count (since midnight local time)
        # Note: alert_time is TIMESTAMP WITH TIME ZONE
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = await conn.fetchval(
            "SELECT COUNT(*) FROM screener_alerts WHERE alert_time >= $1",
            today_start
        )
        print(f"Alerts fired today (since {today_start}): {today_count}")
        
        # Get the last 10 alerts
        rows = await conn.fetch(
            "SELECT symbol, alert_time, trigger_price, rel_vol, alert_type, sent FROM screener_alerts ORDER BY alert_time DESC LIMIT 10"
        )
        print("\nLast 10 alerts:")
        for r in rows:
            print(f"{r['alert_time']} | {r['symbol']:<6} | Price: {r['trigger_price']:<6} | RVOL: {r['rel_vol']:<5} | Type: {r['alert_type']:<15} | Sent: {r['sent']}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
