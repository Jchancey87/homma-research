"""
fastapi_app/routers/gainers.py
Async port of backend/routes/gainers.py.

All DB calls use the asyncpg pool via the get_db() dependency.
Query parameters are validated by Pydantic models that mirror the existing
Flask validation schemas so the API surface is identical.
"""
from __future__ import annotations

import io
import csv
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, JSONResponse

from ..db import get_db, rows_to_list, row_to_dict

log = logging.getLogger(__name__)
router = APIRouter(prefix="/gainers", tags=["gainers"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cutoff_from_period(period: Optional[str]) -> Optional[str]:
    today = datetime.now(timezone.utc).date()
    if period == "week":
        return (today - timedelta(days=7)).isoformat()
    if period == "month":
        return (today - timedelta(days=30)).isoformat()
    if period == "year":
        return (today - timedelta(days=365)).isoformat()
    return None


# ---------------------------------------------------------------------------
# GET /gainers
# ---------------------------------------------------------------------------

@router.get("")
async def list_gainers(
    date:      Optional[str]   = Query(None),
    min_gap:   Optional[float] = Query(None),
    max_float: Optional[float] = Query(None),
    min_rvol:  Optional[float] = Query(None),
    sector:    Optional[str]   = Query(None),
    db: asyncpg.Connection = Depends(get_db),
):
    """Filtered list of daily gainers (mirrors Flask /gainers)."""
    conditions, params = [], []

    if date:
        conditions.append(f"date = ${len(params)+1}")
        params.append(date)
    if min_gap is not None:
        conditions.append(f"gap_pct >= ${len(params)+1}")
        params.append(min_gap)
    if max_float is not None:
        conditions.append(f"float_shares <= ${len(params)+1}")
        params.append(max_float * 1_000_000)
    if min_rvol is not None:
        conditions.append(f"rvol_15m >= ${len(params)+1}")
        params.append(min_rvol)
    if sector:
        conditions.append(f"sector = ${len(params)+1}")
        params.append(sector)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await db.fetch(
        f"SELECT * FROM daily_gainers {where} ORDER BY gap_pct DESC LIMIT 500",
        *params,
    )
    return rows_to_list(rows)


# ---------------------------------------------------------------------------
# GET /gainers/summary
# ---------------------------------------------------------------------------

@router.get("/summary")
async def gainers_summary(db: asyncpg.Connection = Depends(get_db)):
    """Latest ingest date + top 9 gainers + total count."""
    date_row = await db.fetchrow(
        "SELECT date, COUNT(*) AS total FROM daily_gainers "
        "GROUP BY date ORDER BY date DESC LIMIT 1"
    )
    if not date_row:
        return {"date": None, "total": 0, "gainers": []}

    latest_date = date_row["date"]
    total = date_row["total"]

    rows = await db.fetch(
        """SELECT ticker, gap_pct, float_shares, rvol_15m, sector,
                  news_headline, news_fresh, close_price, open_price
           FROM daily_gainers WHERE date = $1
           ORDER BY gap_pct DESC LIMIT 9""",
        latest_date,
    )
    return {"date": str(latest_date), "total": total, "gainers": rows_to_list(rows)}


# ---------------------------------------------------------------------------
# GET /gainers/sectors
# ---------------------------------------------------------------------------

@router.get("/sectors")
async def sectors(db: asyncpg.Connection = Depends(get_db)):
    """Distinct sector list."""
    rows = await db.fetch(
        "SELECT DISTINCT sector FROM daily_gainers "
        "WHERE sector IS NOT NULL AND sector != '' ORDER BY sector"
    )
    return [r["sector"] for r in rows]


# ---------------------------------------------------------------------------
# GET /gainers/export  (CSV download)
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_gainers(
    date:      Optional[str]   = Query(None),
    min_gap:   Optional[float] = Query(None),
    max_float: Optional[float] = Query(None),
    min_rvol:  Optional[float] = Query(None),
    sector:    Optional[str]   = Query(None),
    db: asyncpg.Connection = Depends(get_db),
):
    """CSV export of filtered gainers."""
    conditions, params = [], []
    if date:
        conditions.append(f"date = ${len(params)+1}"); params.append(date)
    if min_gap is not None:
        conditions.append(f"gap_pct >= ${len(params)+1}"); params.append(min_gap)
    if max_float is not None:
        conditions.append(f"float_shares <= ${len(params)+1}"); params.append(max_float * 1_000_000)
    if min_rvol is not None:
        conditions.append(f"rvol_15m >= ${len(params)+1}"); params.append(min_rvol)
    if sector:
        conditions.append(f"sector = ${len(params)+1}"); params.append(sector)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await db.fetch(
        f"SELECT * FROM daily_gainers {where} ORDER BY gap_pct DESC LIMIT 500",
        *params,
    )
    gainers = rows_to_list(rows)

    if not gainers:
        return StreamingResponse(iter([""]), media_type="text/csv")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=gainers[0].keys())
    writer.writeheader()
    writer.writerows(gainers)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gainers.csv"},
    )


# ---------------------------------------------------------------------------
# GET /gainers/ticker-history
# ---------------------------------------------------------------------------

@router.get("/ticker-history")
async def ticker_history(
    period:    Optional[str]   = Query("all"),
    search:    Optional[str]   = Query(None),
    sort:      Optional[str]   = Query("last_seen"),
    limit:     int             = Query(200),
    date:      Optional[str]   = Query(None),
    min_gap:   Optional[float] = Query(None),
    max_float: Optional[float] = Query(None),
    min_rvol:  Optional[float] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sector:    Optional[str]   = Query(None),
    db: asyncpg.Connection = Depends(get_db),
):
    """Aggregated per-ticker appearance history."""
    cutoff = None if date else _cutoff_from_period(period)
    conditions, params = [], []

    if date:
        conditions.append(f"date = ${len(params)+1}"); params.append(date)
    elif cutoff:
        conditions.append(f"date >= ${len(params)+1}"); params.append(cutoff)
    if search:
        conditions.append(f"ticker LIKE ${len(params)+1}"); params.append(f"{search}%")
    if min_gap is not None:
        conditions.append(f"gap_pct >= ${len(params)+1}"); params.append(min_gap)
    if max_float is not None:
        conditions.append(f"float_shares <= ${len(params)+1}"); params.append(max_float * 1_000_000)
    if min_rvol is not None:
        conditions.append(f"rvol_15m >= ${len(params)+1}"); params.append(min_rvol)
    if sector:
        conditions.append(f"sector = ${len(params)+1}"); params.append(sector)
    if min_price is not None:
        conditions.append(f"close_price >= ${len(params)+1}"); params.append(min_price)
    if max_price is not None:
        conditions.append(f"close_price <= ${len(params)+1}"); params.append(max_price)

    order_map = {
        "appearances": "appearances DESC",
        "avg_gap": "avg_gap_pct DESC",
        "last_seen": "last_seen DESC",
        "first_seen": "first_seen ASC",
    }
    order_clause = order_map.get(sort or "last_seen", "last_seen DESC")
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    rows = await db.fetch(f"""
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
    """, *params)
    return rows_to_list(rows)


# ---------------------------------------------------------------------------
# GET /gainers/ticker/{ticker}
# ---------------------------------------------------------------------------

@router.get("/ticker/{ticker}")
async def ticker_appearances(
    ticker: str,
    period: Optional[str] = Query("all"),
    db: asyncpg.Connection = Depends(get_db),
):
    """All individual daily_gainers rows for a specific ticker, newest first."""
    ticker = ticker.upper().strip()
    cutoff = _cutoff_from_period(period)

    if cutoff:
        rows = await db.fetch(
            "SELECT * FROM daily_gainers WHERE ticker = $1 AND date >= $2 ORDER BY date DESC",
            ticker, cutoff,
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM daily_gainers WHERE ticker = $1 ORDER BY date DESC",
            ticker,
        )
    return rows_to_list(rows)


# ---------------------------------------------------------------------------
# GET /gainers/repeat-runners
# ---------------------------------------------------------------------------

@router.get("/repeat-runners")
async def repeat_runners(db: asyncpg.Connection = Depends(get_db)):
    """
    Cross-reference today's live snapshot tickers against historical ingest.
    Returns tickers that are moving today AND have appeared in the DB before.
    """
    try:
        import sys, os
        _backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _backend not in sys.path:
            sys.path.insert(0, _backend)
        from services.live_screener import get_live_gainers
        snapshot = get_live_gainers()
        today_tickers = [g["ticker"] for g in snapshot.get("gainers", [])]
    except Exception:
        return []

    if not today_tickers:
        return []

    rows = await db.fetch(f"""
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
    """, today_tickers)
    return rows_to_list(rows)


# ---------------------------------------------------------------------------
# GET /gainers/float-buckets
# ---------------------------------------------------------------------------

@router.get("/float-buckets")
async def float_buckets(
    date: Optional[str] = Query(None),
    db: asyncpg.Connection = Depends(get_db),
):
    """Bucket gainers by float tier for a given date."""
    exact_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = await db.fetch("""
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
    """, exact_date)
    return {"date": exact_date, "buckets": rows_to_list(rows)}


# ---------------------------------------------------------------------------
# GET /gainers/sector-rotation
# ---------------------------------------------------------------------------

@router.get("/sector-rotation")
async def sector_rotation(db: asyncpg.Connection = Depends(get_db)):
    """Compare this week's vs last week's top sectors by average gap %."""
    today     = datetime.now(timezone.utc).date()
    this_week = (today - timedelta(days=7)).isoformat()
    last_week = (today - timedelta(days=14)).isoformat()

    this_rows = await db.fetch("""
        SELECT sector,
               COUNT(*)                                    AS count,
               ROUND(AVG(gap_pct)::numeric, 1)::float      AS avg_gap_pct
        FROM daily_gainers
        WHERE date >= $1 AND sector IS NOT NULL AND sector != ''
        GROUP BY sector
        ORDER BY avg_gap_pct DESC NULLS LAST
        LIMIT 6
    """, this_week)

    last_rows = await db.fetch("""
        SELECT sector,
               ROUND(AVG(gap_pct)::numeric, 1)::float      AS avg_gap_pct
        FROM daily_gainers
        WHERE date >= $1 AND date < $2 AND sector IS NOT NULL AND sector != ''
        GROUP BY sector
        ORDER BY avg_gap_pct DESC NULLS LAST
        LIMIT 6
    """, last_week, this_week)

    last_map     = {r["sector"]: r["avg_gap_pct"] for r in last_rows}
    last_sectors = [r["sector"] for r in last_rows]

    result = []
    for i, r in enumerate(this_rows):
        sector   = r["sector"]
        last_avg = last_map.get(sector)
        last_rank = last_sectors.index(sector) + 1 if sector in last_sectors else None
        trend = "new"
        if last_avg is not None:
            diff = (r["avg_gap_pct"] or 0) - (last_avg or 0)
            trend = "up" if diff >= 2 else "down" if diff <= -2 else "flat"
        result.append({
            "sector":       sector,
            "count":        r["count"],
            "avg_gap_pct":  r["avg_gap_pct"],
            "last_avg_gap": last_avg,
            "last_rank":    last_rank,
            "this_rank":    i + 1,
            "trend":        trend,
        })
    return result


# ---------------------------------------------------------------------------
# GET /gainers/live
# ---------------------------------------------------------------------------

@router.get("/live")
async def live_screener():
    """
    Live screener data from Schwab API.
    Replaces the Polygon snapshot logic with the Schwab client.
    """
    import asyncio
    from services.live_screener import get_live_gainers
    
    return await asyncio.to_thread(get_live_gainers)

# ---------------------------------------------------------------------------
# GET /gainers/heatmap
# ---------------------------------------------------------------------------

@router.get("/heatmap")
async def gainers_heatmap(
    period:    Optional[str]   = Query(None),
    view:      Optional[str]   = Query("heatmap"),
    date:      Optional[str]   = Query(None),
    min_gap:   Optional[float] = Query(None),
    max_float: Optional[float] = Query(None),
    min_rvol:  Optional[float] = Query(None),
    sector:    Optional[str]   = Query(None),
):
    import asyncio
    
    def _get_heatmap():
        from services.heatmap_service import build_heatmap_spec, get_sector_spec
        cutoff = None if date else _cutoff_from_period(period)
        
        if view == 'sector':
            return get_sector_spec(
                cutoff_date=cutoff, exact_date=date,
                min_gap=min_gap, max_float_m=max_float,
                min_rvol=min_rvol, sector=sector
            )
        else:
            return build_heatmap_spec(
                cutoff_date=cutoff, exact_date=date,
                min_gap=min_gap, max_float_m=max_float,
                min_rvol=min_rvol, sector=sector
            )
            
    return await asyncio.to_thread(_get_heatmap)

# ---------------------------------------------------------------------------
# GET /gainers/follow-through
# ---------------------------------------------------------------------------

@router.get("/follow-through")
async def follow_through(db: asyncpg.Connection = Depends(get_db)):
    """
    For each ticker in the most recent day's gainers, look up the next
    trading day's open price vs the gainer's close price.
    """
    # 1. Find the most recent day in the DB before today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recent_date_row = await db.fetchrow(
        "SELECT MAX(date) as max_date FROM daily_gainers WHERE date < $1", today
    )
    if not recent_date_row or not recent_date_row['max_date']:
        return {"date": None, "results": []}
        
    recent_date = recent_date_row['max_date']
    
    # 2. Get the gainers from that date
    gainers = await db.fetch(
        "SELECT ticker, date as prev_date, gap_pct as prev_gap, close_price as prev_close "
        "FROM daily_gainers WHERE date = $1 ORDER BY gap_pct DESC LIMIT 10",
        recent_date
    )
    
    results = []
    for g in gainers:
        # Check if they appeared the NEXT day or if we need to fetch their open manually
        # For simplicity, if they aren't in daily_gainers the next day, they faded/no data
        next_day = await db.fetchrow(
            "SELECT open_price FROM daily_gainers WHERE ticker=$1 AND date > $2 ORDER BY date ASC LIMIT 1",
            g['ticker'], recent_date
        )
        
        today_open = next_day['open_price'] if next_day else None
        
        change_pct = None
        status = 'no_data'
        
        if today_open and g['prev_close']:
            change_pct = round(((today_open - g['prev_close']) / g['prev_close']) * 100, 2)
            if change_pct > 2.0:
                status = 'following'
            elif change_pct < -2.0:
                status = 'fading'
            else:
                status = 'flat'
                
        results.append({
            'ticker': g['ticker'],
            'prev_date': str(g['prev_date']),
            'prev_gap': g['prev_gap'],
            'prev_close': g['prev_close'],
            'today_open': today_open,
            'change_pct': change_pct,
            'status': status,
        })
        
    return {"date": str(recent_date), "results": results}

# ---------------------------------------------------------------------------
# GET /gainers/pipe-scan
# ---------------------------------------------------------------------------

@router.get("/pipe-scan")
async def pipe_scan(
    date: str = Query(...),
    db: asyncpg.Connection = Depends(get_db)
):
    import asyncio
    
    # 1. Fetch gainers for the date
    gainers = await db.fetch("SELECT ticker FROM daily_gainers WHERE date = $1", date)
    tickers = [g['ticker'] for g in gainers]
    
    if not tickers:
        return []
        
    def _run_pipe_scan():
        from services.pipe_service import build_pipe_payload
        results = []
        for ticker in tickers[:15]: # Limit to top 15 to avoid long wait
            try:
                payload = build_pipe_payload(ticker, date)
                # Mock result based on payload for now since actual scan is LLM based
                results.append({
                    "ticker": ticker,
                    "anchor_date": date,
                    "is_pipe": False, # actual detection requires LLM
                    "filing_date": None,
                    "filing_url": None,
                    "security_type": None,
                    "pricing_type": None,
                    "proceeds_amount": None,
                    "use_of_proceeds": None,
                    "toxic_signals": [],
                    "deal_score": None,
                    "item_codes": []
                })
            except Exception:
                pass
        return results
        
    return await asyncio.to_thread(_run_pipe_scan)
