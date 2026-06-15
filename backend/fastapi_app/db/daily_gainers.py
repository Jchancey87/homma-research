"""
fastapi_app/db/daily_gainers.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read helpers for the ``daily_gainers`` table (the largest in the project
— ~16 SQL strings were spread across ``routers/gainers.py`` before this
extraction).  Pure read-only here; writes are owned by the ingestion
jobs in ``backend/jobs/``.

Table: daily_gainers
Columns: id, ticker, date, gap_pct, float_shares, rvol_15m, sector,
         close_price, open_price, news_headline, news_fresh, market_cap,
         + a few ingest-time enrichment fields.

Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain values so
routers stay Router-Layer-Rules compliant.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Filter helper
# ---------------------------------------------------------------------------

def _filter_conditions(
    *,
    date: Optional[str] = None,
    min_gap: Optional[float] = None,
    max_float_m: Optional[float] = None,
    min_rvol: Optional[float] = None,
    sector: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    cutoff_date: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[str, list]:
    """
    Build a shared WHERE clause for the simple filter endpoints
    (``list_gainers``, ``export_gainers``, etc.).  Each ``None``/empty
    value is omitted, so the caller always sees the same param ordering
    used in the original inline SQL.

    Returns ``(where_clause, params)`` where ``where_clause`` is either
    ``""`` or starts with ``"WHERE "``.
    """
    conditions: list[str] = []
    params: list = []

    if date is not None:
        conditions.append(f"date = ${len(params) + 1}")
        params.append(date)
    elif cutoff_date is not None:
        conditions.append(f"date >= ${len(params) + 1}")
        params.append(cutoff_date)

    if search is not None:
        conditions.append(f"ticker LIKE ${len(params) + 1}")
        params.append(f"{search}%")

    if min_gap is not None:
        conditions.append(f"gap_pct >= ${len(params) + 1}")
        params.append(min_gap)

    if max_float_m is not None:
        # Frontend passes millions; SQL column is raw shares.
        conditions.append(f"float_shares <= ${len(params) + 1}")
        params.append(max_float_m * 1_000_000)

    if min_rvol is not None:
        conditions.append(f"rvol_15m >= ${len(params) + 1}")
        params.append(min_rvol)

    if sector is not None:
        conditions.append(f"sector = ${len(params) + 1}")
        params.append(sector)

    if min_price is not None:
        conditions.append(f"close_price >= ${len(params) + 1}")
        params.append(min_price)

    if max_price is not None:
        conditions.append(f"close_price <= ${len(params) + 1}")
        params.append(max_price)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


# ---------------------------------------------------------------------------
# Simple filter reads
# ---------------------------------------------------------------------------

async def list_gainers(
    conn: asyncpg.Connection,
    *,
    date: Optional[str] = None,
    min_gap: Optional[float] = None,
    max_float_m: Optional[float] = None,
    min_rvol: Optional[float] = None,
    sector: Optional[str] = None,
    limit: int = 500,
) -> list[dict]:
    """Filtered list of daily_gainers rows, ordered by gap_pct DESC."""
    where, params = _filter_conditions(
        date=date, min_gap=min_gap, max_float_m=max_float_m,
        min_rvol=min_rvol, sector=sector,
    )
    rows = await conn.fetch(
        f"SELECT * FROM daily_gainers {where} "
        f"ORDER BY gap_pct DESC LIMIT {limit}",
        *params,
    )
    return [dict(r) for r in rows]


async def tickers_for_date(conn: asyncpg.Connection, date: str) -> list[str]:
    """Distinct tickers that appeared in daily_gainers on the given date."""
    rows = await conn.fetch("SELECT ticker FROM daily_gainers WHERE date = $1", date)
    return [r["ticker"] for r in rows]


async def distinct_sectors(conn: asyncpg.Connection) -> list[str]:
    """Sorted distinct non-empty sector list."""
    rows = await conn.fetch(
        "SELECT DISTINCT sector FROM daily_gainers "
        "WHERE sector IS NOT NULL AND sector != '' ORDER BY sector"
    )
    return [r["sector"] for r in rows]


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

async def latest_ingest_summary(conn: asyncpg.Connection) -> Optional[dict]:
    """Return ``{date, total}`` for the most recent ingest, or None if empty."""
    row = await conn.fetchrow(
        "SELECT date, COUNT(*) AS total FROM daily_gainers "
        "GROUP BY date ORDER BY date DESC LIMIT 1"
    )
    if not row:
        return None
    return {"date": row["date"], "total": row["total"]}


async def top_gainers_on_date(
    conn: asyncpg.Connection,
    target_date,
    limit: int = 9,
) -> list[dict]:
    """Top gainers for a given date, ordered by gap_pct DESC."""
    rows = await conn.fetch(
        """SELECT ticker, gap_pct, float_shares, rvol_15m, sector,
                  news_headline, news_fresh, close_price, open_price
           FROM daily_gainers WHERE date = $1
           ORDER BY gap_pct DESC LIMIT $2""",
        target_date, limit,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Ticker history (aggregated)
# ---------------------------------------------------------------------------

async def aggregate_ticker_history(
    conn: asyncpg.Connection,
    *,
    date: Optional[str] = None,
    cutoff_date: Optional[str] = None,
    search: Optional[str] = None,
    min_gap: Optional[float] = None,
    max_float_m: Optional[float] = None,
    min_rvol: Optional[float] = None,
    sector: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: str = "last_seen",
    limit: int = 200,
) -> list[dict]:
    """Per-ticker appearance history with avg/max aggregates."""
    where, params = _filter_conditions(
        date=date, min_gap=min_gap, max_float_m=max_float_m,
        min_rvol=min_rvol, sector=sector, min_price=min_price, max_price=max_price,
        cutoff_date=cutoff_date, search=search,
    )
    order_map = {
        "appearances": "appearances DESC",
        "avg_gap":     "avg_gap_pct DESC",
        "last_seen":   "last_seen DESC",
        "first_seen":  "first_seen ASC",
    }
    order_clause = order_map.get(sort or "last_seen", "last_seen DESC")
    params.append(limit)

    rows = await conn.fetch(
        f"""
        SELECT
            ticker,
            MAX(sector)                         AS sector,
            COUNT(*)                            AS appearances,
            MAX(date)                           AS last_seen,
            MIN(date)                           AS first_seen,
            ROUND(AVG(gap_pct)::numeric,  2)::float             AS avg_gap_pct,
            ROUND(AVG(rvol_15m)::numeric, 2)::float             AS avg_rvol,
            ROUND((AVG(float_shares) / 1e6)::numeric, 2)::float AS avg_float_m,
            MAX(gap_pct)::float                                  AS max_gap_pct,
            MAX(close_price)::float                              AS last_close,
            MAX(market_cap)::float                               AS last_market_cap
        FROM daily_gainers
        {where}
        GROUP BY ticker
        ORDER BY {order_clause}
        LIMIT ${len(params)}
        """,
        *params,
    )
    return [dict(r) for r in rows]


async def list_appearances_for_ticker(
    conn: asyncpg.Connection,
    ticker: str,
    cutoff_date: Optional[str] = None,
) -> list[dict]:
    """All individual daily_gainers rows for a ticker, newest first."""
    if cutoff_date:
        rows = await conn.fetch(
            "SELECT * FROM daily_gainers WHERE ticker = $1 AND date >= $2 "
            "ORDER BY date DESC",
            ticker, cutoff_date,
        )
    else:
        rows = await conn.fetch(
            "SELECT * FROM daily_gainers WHERE ticker = $1 ORDER BY date DESC",
            ticker,
        )
    return [dict(r) for r in rows]


async def aggregate_repeat_runners(
    conn: asyncpg.Connection,
    tickers: list[str],
) -> list[dict]:
    """For a list of tickers, return historical aggregates sorted by appearances."""
    if not tickers:
        return []
    rows = await conn.fetch(
        """
        SELECT
            ticker,
            COUNT(*)                                           AS appearances,
            ROUND(AVG(gap_pct)::numeric, 1)::float             AS avg_gap_pct,
            MAX(gap_pct)::float                                AS best_gap_pct,
            MAX(date)                                          AS last_seen,
            MIN(date)                                          AS first_seen,
            ROUND(AVG(rvol_15m)::numeric, 1)::float           AS avg_rvol,
            ROUND((AVG(float_shares)/1e6)::numeric, 1)::float AS avg_float_m
        FROM daily_gainers
        WHERE ticker = ANY($1::text[])
        GROUP BY ticker
        ORDER BY appearances DESC, best_gap_pct DESC
        """,
        tickers,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Float-bucket + sector-rotation aggregations
# ---------------------------------------------------------------------------

async def bucket_gainers_by_float(conn: asyncpg.Connection, target_date) -> list[dict]:
    """Bucket gainers by float tier for a given date."""
    rows = await conn.fetch(
        """
        SELECT
            CASE
                WHEN float_shares < 10e6   THEN 'Nano'
                WHEN float_shares < 50e6   THEN 'Micro'
                WHEN float_shares < 200e6  THEN 'Small'
                ELSE                            'Mid+'
            END                                                AS bucket,
            COUNT(*)                                           AS count,
            ROUND(AVG(gap_pct)::numeric, 1)::float             AS avg_gap_pct,
            MAX(gap_pct)::float                                AS best_gap_pct
        FROM daily_gainers
        WHERE date = $1 AND float_shares IS NOT NULL
        GROUP BY bucket
        ORDER BY avg_gap_pct DESC NULLS LAST
        """,
        target_date,
    )
    return [dict(r) for r in rows]


async def sector_aggregates(
    conn: asyncpg.Connection,
    since_date: str,
    before_date: Optional[str] = None,
    limit: int = 6,
) -> list[dict]:
    """
    Per-sector aggregates (count, avg_gap_pct) for the window
    ``[since_date, before_date)`` (or ``[since_date, ∞)`` if
    ``before_date`` is None).
    """
    if before_date is None:
        rows = await conn.fetch(
            """
            SELECT sector,
                   COUNT(*)                                    AS count,
                   ROUND(AVG(gap_pct)::numeric, 1)::float      AS avg_gap_pct
            FROM daily_gainers
            WHERE date >= $1 AND sector IS NOT NULL AND sector != ''
            GROUP BY sector
            ORDER BY avg_gap_pct DESC NULLS LAST
            LIMIT $2
            """,
            since_date, limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT sector,
                   ROUND(AVG(gap_pct)::numeric, 1)::float      AS avg_gap_pct
            FROM daily_gainers
            WHERE date >= $1 AND date < $2 AND sector IS NOT NULL AND sector != ''
            GROUP BY sector
            ORDER BY avg_gap_pct DESC NULLS LAST
            LIMIT $3
            """,
            since_date, before_date, limit,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Follow-through (next-day price lookup)
# ---------------------------------------------------------------------------

async def previous_trading_date(
    conn: asyncpg.Connection,
    today: str,
) -> Optional[str]:
    """The most recent ``daily_gainers.date`` strictly before ``today``."""
    row = await conn.fetchrow(
        "SELECT MAX(date) AS max_date FROM daily_gainers WHERE date < $1",
        today,
    )
    if not row or row["max_date"] is None:
        return None
    return row["max_date"]


async def top_gainers_for_follow_through(
    conn: asyncpg.Connection,
    recent_date,
    limit: int = 10,
) -> list[dict]:
    """Top-N gainers for ``recent_date`` (by gap_pct DESC), for the
    follow-through endpoint."""
    rows = await conn.fetch(
        """SELECT ticker, date AS prev_date, gap_pct AS prev_gap,
                  close_price AS prev_close, float_shares
           FROM daily_gainers WHERE date = $1
           ORDER BY gap_pct DESC LIMIT $2""",
        recent_date, limit,
    )
    return [dict(r) for r in rows]


async def next_trading_day_for_ticker(
    conn: asyncpg.Connection,
    ticker: str,
    after_date,
) -> Optional[dict]:
    """First daily_gainers row for ``ticker`` strictly after ``after_date``,
    used as the follow-through fallback when no live quote is available."""
    row = await conn.fetchrow(
        """SELECT open_price, close_price FROM daily_gainers
           WHERE ticker = $1 AND date > $2
           ORDER BY date ASC LIMIT 1""",
        ticker, after_date,
    )
    return dict(row) if row else None
