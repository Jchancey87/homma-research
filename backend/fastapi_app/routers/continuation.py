"""
fastapi_app/routers/continuation.py
Async port of backend/routes/continuation_picks.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from ..db import get_db, rows_to_list, row_to_dict
from validation.schemas import PickAddBody

log = logging.getLogger(__name__)
router = APIRouter(prefix="/continuation-picks", tags=["continuation"])


class DeactivateBody(BaseModel):
    reason: str = "manually dismissed"


@router.get("")
async def list_picks(
    include_inactive: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    db: asyncpg.Connection = Depends(get_db),
):
    import asyncio
    
    if include_inactive:
        rows = await db.fetch(
            """SELECT * FROM continuation_picks
               ORDER BY is_active DESC, date DESC, rank ASC
               LIMIT $1""",
            limit,
        )
    else:
        rows = await db.fetch(
            """SELECT * FROM continuation_picks
               WHERE is_active = TRUE
               ORDER BY date DESC, rank ASC
               LIMIT $1""",
            limit,
        )
    
    results = rows_to_list(rows)
    if not results:
        return results
        
    tickers = {r["ticker"] for r in results}
    try:
        from momentum_screener.schwab.http_client import get_quotes
        quotes = await asyncio.to_thread(get_quotes, list(tickers))
    except Exception as e:
        log.warning(f"Failed to fetch live quotes for continuation picks: {e}")
        quotes = {}
        
    for r in results:
        ticker = r["ticker"]
        q_data = quotes.get(ticker, {}) if quotes else {}
        quote = q_data.get('quote', {}) if q_data else {}
        
        r["today_last"] = quote.get("lastPrice")
        r["today_open"] = quote.get("openPrice")
        r["today_volume"] = quote.get("totalVolume")
        r["today_change_pct"] = quote.get("netPercentChange")
        
    return results


@router.post("", status_code=201)
async def add_picks(data: PickAddBody, db: asyncpg.Connection = Depends(get_db)):
    """Batch-insert continuation picks (idempotent via ON CONFLICT DO NOTHING)."""
    now = datetime.now(timezone.utc)
    inserted = 0
    for p in data.picks:
        await db.execute(
            """INSERT INTO continuation_picks
               (ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (ticker, date) DO NOTHING""",
            p.ticker, p.date.isoformat(), p.reason, p.gap_pct,
            p.float_shares, p.rvol_15m, p.sector, p.rank, now,
        )
        inserted += 1
    return {"inserted": inserted}


@router.post("/{pick_id}/deactivate")
async def deactivate_pick(
    pick_id: int,
    body: DeactivateBody = Body(default_factory=DeactivateBody),
    db: asyncpg.Connection = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    row = await db.fetchrow("SELECT id FROM continuation_picks WHERE id = $1", pick_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await db.execute(
        """UPDATE continuation_picks
           SET is_active = FALSE, deactivated_at = $1, deactivated_reason = $2
           WHERE id = $3""",
        now, body.reason, pick_id,
    )
    return {"success": True}


@router.delete("/{pick_id}")
async def delete_pick(pick_id: int, db: asyncpg.Connection = Depends(get_db)):
    row = await db.fetchrow("SELECT id FROM continuation_picks WHERE id = $1", pick_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await db.execute("DELETE FROM continuation_picks WHERE id = $1", pick_id)
    return {"success": True}


@router.get("/stats")
async def picks_stats(db: asyncpg.Connection = Depends(get_db)):
    rows = await db.fetch(
        """SELECT date, COUNT(*) AS count
           FROM continuation_picks
           WHERE is_active = TRUE
           GROUP BY date
           ORDER BY date DESC
           LIMIT 14"""
    )
    return rows_to_list(rows)


@router.post("/refresh-performance")
async def refresh_performance():
    """Manually triggers performance historical tracking update."""
    import asyncio
    from services.continuation_performance_service import update_all_continuation_performances
    count = await asyncio.to_thread(update_all_continuation_performances)
    return {"updated": count}


@router.get("/performance")
async def get_performance_stats(db: asyncpg.Connection = Depends(get_db)):
    """Computes a statistical scorecard of continuation picks performance."""
    rows = await db.fetch(
        """SELECT ticker, date, gap_pct, float_shares, sector, rank, close_d0,
                  d1_open, d1_high, d1_low, d1_close, d1_volume,
                  d2_open, d2_high, d2_low, d2_close, d2_volume,
                  d3_open, d3_high, d3_low, d3_close, d3_volume,
                  market_cap, shares_outstanding, cash, runway_months, dilution_risk, news_fresh
           FROM continuation_picks
           WHERE close_d0 IS NOT NULL"""
    )
    picks = rows_to_list(rows)
    if not picks:
        return {"summary": {}, "groups": {}}

    # Calculate metrics per pick
    completed_picks = []
    for p in picks:
        c0 = p['close_d0']
        if not c0 or c0 <= 0:
            continue
            
        d1_h, d2_h, d3_h = p['d1_high'], p['d2_high'], p['d3_high']
        d1_c, d2_c, d3_c = p['d1_close'], p['d2_close'], p['d3_close']
        
        # Max extension over the 3 days
        highs = [h for h in [d1_h, d2_h, d3_h] if h is not None]
        max_high = max(highs) if highs else c0
        max_ext = ((max_high - c0) / c0) * 100
        
        # Day 1 return
        d1_ret = ((d1_c - c0) / c0) * 100 if d1_c else 0.0
        
        # Day 2 return
        d2_ret = ((d2_c - c0) / c0) * 100 if d2_c else 0.0
        
        # Day 3 return
        d3_ret = ((d3_c - c0) / c0) * 100 if d3_c else 0.0
        
        # Win is defined as max extension >= 10% (reasonable continuation)
        is_win = max_ext >= 10.0
        # Super win is >= 30%
        is_super_win = max_ext >= 30.0
        
        # Categorize float
        f = p['float_shares']
        if f is None:
            float_cat = "Unknown"
        elif f < 5e6:
            float_cat = "< 5M"
        elif f < 10e6:
            float_cat = "5M - 10M"
        elif f < 50e6:
            float_cat = "10M - 50M"
        else:
            float_cat = "> 50M"
            
        # Categorize Gap
        g = p['gap_pct']
        if g is None:
            gap_cat = "Unknown"
        elif g < 20.0:
            gap_cat = "< 20%"
        elif g < 40.0:
            gap_cat = "20% - 40%"
        else:
            gap_cat = "> 40%"

        # Categorize Dilution Risk
        dil = p['dilution_risk'] or "Unknown"

        completed_picks.append({
            'ticker': p['ticker'],
            'max_ext': max_ext,
            'd1_ret': d1_ret,
            'd2_ret': d2_ret,
            'd3_ret': d3_ret,
            'is_win': is_win,
            'is_super_win': is_super_win,
            'float_cat': float_cat,
            'gap_cat': gap_cat,
            'sector': p['sector'] or "Unknown",
            'dilution_risk': dil,
            'news_fresh': p['news_fresh']
        })

    if not completed_picks:
        return {"summary": {}, "groups": {}}

    # Compute overall summary
    total = len(completed_picks)
    wins = sum(1 for p in completed_picks if p['is_win'])
    super_wins = sum(1 for p in completed_picks if p['is_super_win'])
    avg_max_ext = sum(p['max_ext'] for p in completed_picks) / total
    avg_d1_ret = sum(p['d1_ret'] for p in completed_picks) / total
    avg_d3_ret = sum(p['d3_ret'] for p in completed_picks) / total

    summary = {
        "total_picks": total,
        "win_rate": round((wins / total) * 100, 1),
        "super_win_rate": round((super_wins / total) * 100, 1),
        "avg_max_ext": round(avg_max_ext, 1),
        "avg_d1_ret": round(avg_d1_ret, 1),
        "avg_d3_ret": round(avg_d3_ret, 1)
    }

    # Group statistics helper
    def get_group_stats(group_key):
        grouped = {}
        for p in completed_picks:
            val = p[group_key]
            if val not in grouped:
                grouped[val] = []
            grouped[val].append(p)
            
        stats = []
        for name, items in grouped.items():
            g_total = len(items)
            g_wins = sum(1 for x in items if x['is_win'])
            g_super = sum(1 for x in items if x['is_super_win'])
            g_avg_ext = sum(x['max_ext'] for x in items) / g_total
            stats.append({
                "group_value": str(name),
                "count": g_total,
                "win_rate": round((g_wins / g_total) * 100, 1),
                "super_win_rate": round((g_super / g_total) * 100, 1),
                "avg_max_ext": round(g_avg_ext, 1)
            })
        stats.sort(key=lambda x: x['count'], reverse=True)
        return stats

    groups = {
        "float_category": get_group_stats("float_cat"),
        "gap_category": get_group_stats("gap_cat"),
        "sector": get_group_stats("sector"),
        "dilution_risk": get_group_stats("dilution_risk"),
        "news_freshness": get_group_stats("news_fresh")
    }

    return {"summary": summary, "groups": groups}
