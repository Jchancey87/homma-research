"""
fastapi_app/db/market.py
~~~~~~~~~~~~~~~~~~~~~~~~
Read helpers for the market-router's three SQL queries.

Two tables touched:
  - daily_gainers    — used by ``GET /market/momentum-breadth`` to compute
                       the top-5 RVOL/float fallback when the in-process
                       live cache is empty.
  - volatility_halts — used by the same endpoint to list tickers that are
                       currently in a volatility halt.

Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain values
so routers stay Router-Layer-Rules compliant.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# daily_gainers — used for the momentum-breadth DB fallback
# ---------------------------------------------------------------------------

async def latest_daily_gainers_date(conn: asyncpg.Connection) -> Optional[date]:
    """Return the most recent date in ``daily_gainers``, or None if empty."""
    row = await conn.fetchrow("SELECT MAX(date) AS max_date FROM daily_gainers")
    if not row or row["max_date"] is None:
        return None
    return row["max_date"]


async def top_rvol_float_on_date(
    conn: asyncpg.Connection,
    target_date: date,
    *,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 5,
) -> list[dict]:
    """
    Top-N rows from ``daily_gainers`` on ``target_date`` ordered by gap_pct
    DESC.  Optional ``min_price``/``max_price`` restrict to a price band.
    Returns rows with at least ``rvol_15m`` and ``float_shares`` populated;
    the caller is expected to filter out None values when aggregating.
    """
    conditions = ["date = $1"]
    params: list = [target_date]

    if min_price is not None and max_price is not None:
        conditions.append("close_price BETWEEN $2 AND $3")
        params.extend([min_price, max_price])

    where = " AND ".join(conditions)
    rows = await conn.fetch(
        f"""
        SELECT rvol_15m, float_shares
        FROM daily_gainers
        WHERE {where}
        ORDER BY gap_pct DESC
        LIMIT {limit}
        """,
        *params,
    )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# volatility_halts — currently active halts
# ---------------------------------------------------------------------------

async def active_volatility_halts_last_hour(conn: asyncpg.Connection) -> list[str]:
    """
    Tickers that are currently in a volatility halt (status = 'halted')
    and halted within the last 60 minutes.  Used by the
    momentum-breadth endpoint's halt-tracker block.
    """
    rows = await conn.fetch(
        """
        SELECT DISTINCT ticker FROM volatility_halts
        WHERE halt_time >= NOW() - INTERVAL '60 minutes'
          AND status = 'halted'
        ORDER BY ticker
        """
    )
    return [r["ticker"] for r in rows]
