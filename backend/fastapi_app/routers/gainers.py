"""
fastapi_app/routers/gainers.py
Async port of backend/routes/gainers.py.

All DB calls use the asyncpg pool via the get_db() dependency.
Query parameters are validated by Pydantic models that mirror the existing
Flask validation schemas so the API surface is identical.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..db import daily_gainers as db_daily_gainers
from services.live_quotes_service import get_live_quotes
from validation import normalize_ticker

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
    return await db_daily_gainers.list_gainers(
        db,
        date=date,
        min_gap=min_gap,
        max_float_m=max_float,
        min_rvol=min_rvol,
        sector=sector,
    )


# ---------------------------------------------------------------------------
# GET /gainers/summary
# ---------------------------------------------------------------------------

@router.get("/summary")
async def gainers_summary(db: asyncpg.Connection = Depends(get_db)):
    """Latest ingest date + top 9 gainers + total count."""
    summary = await db_daily_gainers.latest_ingest_summary(db)
    if not summary:
        return {"date": None, "total": 0, "gainers": []}

    top = await db_daily_gainers.top_gainers_on_date(db, summary["date"], limit=9)
    return {
        "date": str(summary["date"]),
        "total": summary["total"],
        "gainers": top,
    }


# ---------------------------------------------------------------------------
# GET /gainers/sectors
# ---------------------------------------------------------------------------

@router.get("/sectors")
async def sectors(db: asyncpg.Connection = Depends(get_db)):
    """Distinct sector list."""
    return await db_daily_gainers.distinct_sectors(db)


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
    rows = await db_daily_gainers.list_gainers(
        db,
        date=date,
        min_gap=min_gap,
        max_float_m=max_float,
        min_rvol=min_rvol,
        sector=sector,
    )
    if not rows:
        return StreamingResponse(iter([""]), media_type="text/csv")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

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
    return await db_daily_gainers.aggregate_ticker_history(
        db,
        date=date,
        cutoff_date=cutoff,
        search=search,
        min_gap=min_gap,
        max_float_m=max_float,
        min_rvol=min_rvol,
        sector=sector,
        min_price=min_price,
        max_price=max_price,
        sort=sort or "last_seen",
        limit=limit,
    )


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
    cutoff = _cutoff_from_period(period)
    return await db_daily_gainers.list_appearances_for_ticker(
        db, normalize_ticker(ticker), cutoff_date=cutoff
    )


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
        from services.live_screener import get_live_gainers
        snapshot = await asyncio.to_thread(get_live_gainers)
        gainers_by_ticker = {g["ticker"]: g for g in snapshot.get("gainers", [])}
        today_tickers = list(gainers_by_ticker.keys())
    except Exception:
        return []

    if not today_tickers:
        return []

    rows = await db_daily_gainers.aggregate_repeat_runners(db, today_tickers)
    for r in rows:
        g = gainers_by_ticker.get(r['ticker'], {})
        r['sparkline_5d'] = g.get('sparkline_5d', [])
        r['sparkline_intraday'] = g.get('sparkline_intraday', [])
        r['sparkline_1h'] = g.get('sparkline_1h', [])
        r['sma20'] = g.get('sma20')
        r['sma50'] = g.get('sma50')
        r['sma100'] = g.get('sma100')
        r['above_sma20'] = g.get('above_sma20', False)
        r['above_sma50'] = g.get('above_sma50', False)
        r['above_sma100'] = g.get('above_sma100', False)
        r['today_last'] = g.get('last_price')
        r['today_gap_pct'] = g.get('gap_pct')
    return rows


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
    buckets = await db_daily_gainers.bucket_gainers_by_float(db, exact_date)
    return {"date": exact_date, "buckets": buckets}


# ---------------------------------------------------------------------------
# GET /gainers/sector-rotation
# ---------------------------------------------------------------------------

@router.get("/sector-rotation")
async def sector_rotation(db: asyncpg.Connection = Depends(get_db)):
    """Compare this week's vs last week's top sectors by average gap %."""
    today     = datetime.now(timezone.utc).date()
    this_week = (today - timedelta(days=7)).isoformat()
    last_week = (today - timedelta(days=14)).isoformat()

    this_rows = await db_daily_gainers.sector_aggregates(db, since_date=this_week)
    last_rows = await db_daily_gainers.sector_aggregates(
        db, since_date=last_week, before_date=this_week,
    )

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
async def live_screener(force: Optional[int] = Query(None)):
    """Live screener data from Schwab API."""
    from services.live_screener import get_live_gainers
    should_force = (force == 1)
    return await asyncio.to_thread(get_live_gainers, force=should_force)


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
    def _get_heatmap():
        from services.heatmap_service import build_heatmap_spec, get_sector_spec
        cutoff = None if date else _cutoff_from_period(period)

        if view == 'sector':
            return get_sector_spec(
                cutoff_date=cutoff, exact_date=date,
                min_gap=min_gap, max_float_m=max_float,
                min_rvol=min_rvol, sector=sector,
            )
        return build_heatmap_spec(
            cutoff_date=cutoff, exact_date=date,
            min_gap=min_gap, max_float_m=max_float,
            min_rvol=min_rvol, sector=sector,
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    recent_date = await db_daily_gainers.previous_trading_date(db, today)
    if not recent_date:
        return {"date": None, "results": []}

    gainers = await db_daily_gainers.top_gainers_for_follow_through(db, recent_date, limit=10)
    if not gainers:
        return {"date": str(recent_date), "results": []}

    tickers = [g["ticker"] for g in gainers]
    # No Polygon fallback here: subsequent trading days may not be in the
    # Polygon snapshot cache, and the DB lookup below already covers the
    # historical-day case.
    quotes = await get_live_quotes(tickers)

    results = []
    for g in gainers:
        ticker = g["ticker"]
        nq = quotes.get(ticker)

        if nq is not None and nq.source != "none":
            today_open   = nq.open_price
            today_last   = nq.last_price
            today_volume = nq.volume
        else:
            next_day = await db_daily_gainers.next_trading_day_for_ticker(
                db, ticker, recent_date
            )
            if next_day:
                today_open   = next_day["open_price"]
                today_last   = next_day["close_price"]
                today_volume = None
            else:
                today_open = today_last = today_volume = None

        price_for_calc = today_last if today_last is not None else today_open
        change_pct = None
        status = 'no_data'

        if price_for_calc is not None and g["prev_close"]:
            change_pct = round(((price_for_calc - g["prev_close"]) / g["prev_close"]) * 100, 2)
            if change_pct > 2.0:
                status = 'following'
            elif change_pct < -2.0:
                status = 'fading'
            else:
                status = 'flat'

        results.append({
            'ticker':       ticker,
            'prev_date':    str(g["prev_date"]),
            'prev_gap':     g["prev_gap"],
            'prev_close':   g["prev_close"],
            'today_open':   today_open,
            'today_last':   today_last,
            'today_volume': today_volume,
            'change_pct':   change_pct,
            'status':       status,
            'float_shares': g["float_shares"],
        })

    return {"date": str(recent_date), "results": results}


# ---------------------------------------------------------------------------
# GET /gainers/pipe-scan
# ---------------------------------------------------------------------------

@router.get("/pipe-scan")
async def pipe_scan(
    date: str = Query(...),
    db: asyncpg.Connection = Depends(get_db),
):
    tickers = await db_daily_gainers.tickers_for_date(db, date)
    if not tickers:
        return []

    def _run_pipe_scan():
        from services.pipe_service import build_pipe_payload
        results = []
        for ticker in tickers[:15]:  # Limit to top 15 to avoid long wait
            try:
                payload = build_pipe_payload(ticker, date)
                results.append({
                    "ticker":         ticker,
                    "anchor_date":    date,
                    "is_pipe":        False,  # actual detection requires LLM
                    "filing_date":    None,
                    "filing_url":     None,
                    "security_type":  None,
                    "pricing_type":   None,
                    "proceeds_amount": None,
                    "use_of_proceeds": None,
                    "toxic_signals":  [],
                    "deal_score":     None,
                    "item_codes":     [],
                })
            except Exception:
                pass
        return results

    return await asyncio.to_thread(_run_pipe_scan)
