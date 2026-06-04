import asyncio
import asyncpg

async def main():
    dsn = "postgresql://journal:journal1@192.168.0.201:5432/trading_journal"
    conn = await asyncpg.connect(dsn)
    try:
        print("Truncating stock_fundamentals...")
        await conn.execute("TRUNCATE TABLE stock_fundamentals CASCADE")
        print("Truncated successfully!")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
