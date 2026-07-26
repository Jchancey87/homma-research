"""
Gainers Service.

Business logic for float buckets, sector rotation trend calculations, and ticker history queries.
Follows RFC-001 thin router rules.
"""

from typing import Dict, List, Optional
import asyncpg


async def get_float_buckets_service(db: asyncpg.Pool, target_date: str) -> List[dict]:
    query = """
        SELECT
            CASE
                WHEN float_shares IS NULL THEN 'Unknown'
                WHEN float_shares < 2000000 THEN '<2M (Micro)'
                WHEN float_shares < 5000000 THEN '2M-5M (Low)'
                WHEN float_shares < 10000000 THEN '5M-10M (Mid)'
                WHEN float_shares < 20000000 THEN '10M-20M (High)'
                ELSE '20M+ (Huge)'
            END AS bucket,
            COUNT(*)::int AS count,
            ROUND(AVG(gap_pct)::numeric, 2)::float AS avg_gap_pct,
            ROUND(MAX(gap_pct)::numeric, 2)::float AS best_gap_pct
        FROM daily_gainers
        WHERE date = $1
        GROUP BY bucket
        ORDER BY MIN(float_shares) ASC NULLS LAST;
    """
    rows = await db.fetch(query, target_date)
    return [dict(r) for r in rows]


async def get_sector_rotation_service(db: asyncpg.Pool) -> List[dict]:
    query = """
        WITH latest_dates AS (
            SELECT DISTINCT date FROM daily_gainers ORDER BY date DESC LIMIT 2
        ),
        dated_gainers AS (
            SELECT g.date, g.sector, g.gap_pct
            FROM daily_gainers g
            JOIN latest_dates d ON g.date = d.date
            WHERE g.sector IS NOT NULL
        ),
        sector_stats AS (
            SELECT
                date,
                sector,
                COUNT(*)::int AS count,
                ROUND(AVG(gap_pct)::numeric, 2)::float AS avg_gap_pct,
                RANK() OVER (PARTITION BY date ORDER BY COUNT(*) DESC, AVG(gap_pct) DESC) AS rank
            FROM dated_gainers
            GROUP BY date, sector
        ),
        pivoted AS (
            SELECT
                sector,
                MAX(CASE WHEN date = (SELECT MAX(date) FROM latest_dates) THEN count END) AS this_count,
                MAX(CASE WHEN date = (SELECT MAX(date) FROM latest_dates) THEN avg_gap_pct END) AS this_avg_gap,
                MAX(CASE WHEN date = (SELECT MAX(date) FROM latest_dates) THEN rank END) AS this_rank,
                MAX(CASE WHEN date = (SELECT MIN(date) FROM latest_dates) THEN avg_gap_pct END) AS last_avg_gap,
                MAX(CASE WHEN date = (SELECT MIN(date) FROM latest_dates) THEN rank END) AS last_rank
            FROM sector_stats
            GROUP BY sector
        )
        SELECT
            sector,
            COALESCE(this_count, 0) AS count,
            this_avg_gap AS avg_gap_pct,
            last_avg_gap,
            last_rank::int,
            COALESCE(this_rank, 999)::int AS this_rank,
            CASE
                WHEN last_rank IS NULL THEN 'new'
                WHEN this_rank < last_rank THEN 'up'
                WHEN this_rank > last_rank THEN 'down'
                ELSE 'flat'
            END AS trend
        FROM pivoted
        ORDER BY this_rank ASC, count DESC;
    """
    rows = await db.fetch(query)
    return [dict(r) for r in rows]
