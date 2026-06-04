import asyncio
import asyncpg

async def main():
    dsn = "postgresql://journal:journal1@192.168.0.201:5432/trading_journal"
    conn = await asyncpg.connect(dsn)
    try:
        # Get all table names in public and alerts schemas
        tables = await conn.fetch("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema IN ('public', 'alerts')
            ORDER BY table_schema, table_name
        """)
        print("Tables in database:")
        for t in tables:
            print(f"Schema: {t['table_schema']:<8} | Table: {t['table_name']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
