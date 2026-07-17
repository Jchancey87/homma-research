"""
fastapi_app/routers/watchlist.py
Async port of backend/routes/watchlist.py.

Sync service calls (fmp_service, llm_client, requests) are wrapped in
asyncio.to_thread() to keep the event loop non-blocking.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response

from ..config import settings
from ..db import get_db
from ..db import watchlist as db_watchlist
from validation import normalize_ticker
from validation.schemas import WatchlistAddBody, WatchlistUpdateBody, WatchlistGroupAddBody
from services.live_quotes_service import get_live_quotes
from services.watchlist_service import export_watchlist_to_csv, import_watchlist_from_csv

log = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ---------------------------------------------------------------------------
# GET /watchlist/groups
# ---------------------------------------------------------------------------

@router.get("/groups")
async def list_groups(db: asyncpg.Connection = Depends(get_db)):
    """Return all watchlist groups."""
    return await db_watchlist.list_watchlist_groups(db)


# ---------------------------------------------------------------------------
# POST /watchlist/groups
# ---------------------------------------------------------------------------

@router.post("/groups", status_code=201)
async def create_group(data: WatchlistGroupAddBody, db: asyncpg.Connection = Depends(get_db)):
    """Create a new watchlist group."""
    name = data.name
    if await db_watchlist.watchlist_group_exists_by_name(db, name):
        raise HTTPException(status_code=409, detail=f"Group '{name}' already exists")
    
    return await db_watchlist.insert_watchlist_group(db, name)


# ---------------------------------------------------------------------------
# DELETE /watchlist/groups/{group_id}
# ---------------------------------------------------------------------------

@router.delete("/groups/{group_id}")
async def delete_group(group_id: int, db: asyncpg.Connection = Depends(get_db)):
    """Delete a watchlist group and all its member tickers."""
    deleted = await db_watchlist.delete_watchlist_group(db, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# GET /watchlist
# ---------------------------------------------------------------------------

@router.get("")
async def list_watchlist(db: asyncpg.Connection = Depends(get_db), group_id: Optional[int] = None):
    """Return watchlist tickers, optionally filtered by group_id."""
    return await db_watchlist.list_watchlist(db, group_id=group_id)


# ---------------------------------------------------------------------------
# POST /watchlist
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def add_to_watchlist(data: WatchlistAddBody, db: asyncpg.Connection = Depends(get_db)):
    """Add a ticker to the watchlist, enriching via FMP + LLM if data is sparse."""
    ticker   = data.ticker
    sector   = data.sector
    notes    = data.notes
    tags_raw = list(data.tags)
    group_id = data.group_id

    # Enrich via FMP + LLM if any key field is missing (sync, so offload)
    if not sector or not notes or not tags_raw:
        def _enrich():
            import sys, os
            _backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if _backend not in sys.path:
                sys.path.insert(0, _backend)
            from services.fmp_service import get_company_profile
            from llm.llm_client import get_ticker_enrichment

            profile = get_company_profile(ticker)
            _sector = sector
            _notes  = notes
            _tags   = tags_raw[:]

            if profile:
                if not _sector:
                    _sector = profile.get("sector")
                if not _notes or not _tags:
                    enrich = get_ticker_enrichment(
                        ticker,
                        profile.get("sector", "Unknown"),
                        profile.get("description") or f"A company in the {profile.get('sector', 'Unknown')} sector.",
                    )
                    if not _notes:
                        _notes = enrich.get("notes")
                    if not _tags:
                        _tags = enrich.get("tags") or []
            return _sector, _notes, _tags

        sector, notes, tags_raw = await asyncio.to_thread(_enrich)

    tags_json = json.dumps([str(t).strip() for t in tags_raw if str(t).strip()])

    try:
        await db_watchlist.insert_watchlist(
            db,
            ticker=ticker,
            sector=sector,
            notes=notes,
            tags_json=tags_json,
            group_id=group_id,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail=f"{ticker} is already on your watchlist in this group")

    # Trigger enrichment inline
    from services.watchlist_service import enrich_watchlist_fundamentals
    try:
        await enrich_watchlist_fundamentals(db, group_id=group_id, ticker=ticker)
    except Exception as e:
        log.warning(f"Failed to run inline fundamental enrichment for {ticker}: {e}")

    return {"ticker": ticker}


# ---------------------------------------------------------------------------
# PUT /watchlist/{ticker}
# ---------------------------------------------------------------------------

@router.put("/{ticker}")
async def update_watchlist_item(
    ticker: str,
    data: WatchlistUpdateBody,
    db: asyncpg.Connection = Depends(get_db),
    group_id: Optional[int] = None,
):
    ticker = normalize_ticker(ticker)
    if not await db_watchlist.watchlist_ticker_exists(db, ticker, group_id):
        raise HTTPException(status_code=404, detail="Not found")

    updates: dict = {}
    if data.notes is not None:
        updates["notes"] = data.notes
    if data.sector is not None:
        updates["sector"] = data.sector
    if data.tags is not None:
        updates["tags"] = json.dumps(data.tags)

    await db_watchlist.update_watchlist(db, ticker, updates, group_id)
    return {"success": True}


# ---------------------------------------------------------------------------
# POST /watchlist/{ticker}/viewed
# ---------------------------------------------------------------------------

@router.post("/{ticker}/viewed")
async def mark_viewed(
    ticker: str,
    db: asyncpg.Connection = Depends(get_db),
    group_id: Optional[int] = None,
):
    await db_watchlist.mark_watchlist_viewed(db, normalize_ticker(ticker), group_id=group_id)
    return {"success": True}


# ---------------------------------------------------------------------------
# DELETE /watchlist/{ticker}
# ---------------------------------------------------------------------------

@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    db: asyncpg.Connection = Depends(get_db),
    group_id: Optional[int] = None,
):
    ticker = normalize_ticker(ticker)
    deleted = await db_watchlist.delete_watchlist(db, ticker, group_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# POST /watchlist/enrich
# ---------------------------------------------------------------------------

@router.post("/enrich")
async def enrich_watchlist(
    group_id: Optional[int] = None,
    db: asyncpg.Connection = Depends(get_db)
):
    """Enrich watchlist items with fundamental metrics."""
    from services.watchlist_service import enrich_watchlist_fundamentals
    processed = await enrich_watchlist_fundamentals(db, group_id=group_id)
    return {"success": True, "processed": processed}


# ---------------------------------------------------------------------------
# GET /watchlist/prices
# ---------------------------------------------------------------------------

@router.get("/prices")
async def watchlist_prices(db: asyncpg.Connection = Depends(get_db), group_id: Optional[int] = None):
    """Return Schwab (or Polygon fallback) price + % change for every watchlist ticker in batch."""
    rows = await db_watchlist.list_watchlist(db, group_id=group_id)
    if not rows:
        return {}

    tickers = [r["ticker"] for r in rows]
    quotes = await get_live_quotes(tickers, polygon_api_key=settings.polygon_api_key)
    
    row_map = {r["ticker"].upper(): r for r in rows}
    
    return {
        t: {
            "price":   nq.last_price,
            "chg_pct": nq.change_pct,
            "volume":  nq.volume,
            "runway_months": row_map[t.upper()].get("runway_months"),
            "dilution_risk": row_map[t.upper()].get("dilution_risk"),
            "upcoming_catalyst": row_map[t.upper()].get("upcoming_catalyst"),
            "catalyst_date": row_map[t.upper()].get("catalyst_date") if row_map[t.upper()].get("catalyst_date") is not None else None,
        }
        for t, nq in quotes.items() if t.upper() in row_map
    }


# ---------------------------------------------------------------------------
# GET /watchlist/export
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_watchlist(db: asyncpg.Connection = Depends(get_db), group_id: Optional[int] = None):
    """Export all watchlist tickers in CSV format."""
    csv_data = await export_watchlist_to_csv(db, group_id=group_id)
    filename = "watchlist_export.csv" if not group_id else f"watchlist_group_{group_id}_export.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ---------------------------------------------------------------------------
# POST /watchlist/import
# ---------------------------------------------------------------------------

@router.post("/import")
async def import_watchlist(
    file: UploadFile = File(...),
    db: asyncpg.Connection = Depends(get_db),
    group_id: Optional[int] = None,
):
    """Import tickers from a CSV file."""
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")

    inserted, updated = await import_watchlist_from_csv(db, csv_text, group_id=group_id)
    return {"inserted": inserted, "updated": updated}

