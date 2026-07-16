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
from validation.schemas import WatchlistAddBody, WatchlistUpdateBody
from services.live_quotes_service import get_live_quotes
from services.watchlist_service import export_watchlist_to_csv, import_watchlist_from_csv

log = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ---------------------------------------------------------------------------
# GET /watchlist
# ---------------------------------------------------------------------------

@router.get("")
async def list_watchlist(db: asyncpg.Connection = Depends(get_db)):
    """Return all watchlist tickers ordered by last viewed / added."""
    return await db_watchlist.list_watchlist(db)


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
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail=f"{ticker} is already on your watchlist")

    return {"ticker": ticker}


# ---------------------------------------------------------------------------
# PUT /watchlist/{ticker}
# ---------------------------------------------------------------------------

@router.put("/{ticker}")
async def update_watchlist_item(
    ticker: str,
    data: WatchlistUpdateBody,
    db: asyncpg.Connection = Depends(get_db),
):
    ticker = normalize_ticker(ticker)
    if not await db_watchlist.watchlist_ticker_exists(db, ticker):
        raise HTTPException(status_code=404, detail="Not found")

    updates: dict = {}
    if data.notes is not None:
        updates["notes"] = data.notes
    if data.sector is not None:
        updates["sector"] = data.sector
    if data.tags is not None:
        updates["tags"] = json.dumps(data.tags)

    await db_watchlist.update_watchlist(db, ticker, updates)
    return {"success": True}


# ---------------------------------------------------------------------------
# POST /watchlist/{ticker}/viewed
# ---------------------------------------------------------------------------

@router.post("/{ticker}/viewed")
async def mark_viewed(ticker: str, db: asyncpg.Connection = Depends(get_db)):
    await db_watchlist.mark_watchlist_viewed(db, normalize_ticker(ticker))
    return {"success": True}


# ---------------------------------------------------------------------------
# DELETE /watchlist/{ticker}
# ---------------------------------------------------------------------------

@router.delete("/{ticker}")
async def remove_from_watchlist(ticker: str, db: asyncpg.Connection = Depends(get_db)):
    ticker = normalize_ticker(ticker)
    deleted = await db_watchlist.delete_watchlist(db, ticker)
    if not deleted:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# GET /watchlist/prices
# ---------------------------------------------------------------------------

@router.get("/prices")
async def watchlist_prices(db: asyncpg.Connection = Depends(get_db)):
    """Return Schwab (or Polygon fallback) price + % change for every watchlist ticker in batch."""
    tickers = await db_watchlist.list_watchlist_tickers(db)
    if not tickers:
        return {}

    quotes = await get_live_quotes(tickers, polygon_api_key=settings.polygon_api_key)
    return {
        t: {
            "price":   nq.last_price,
            "chg_pct": nq.change_pct,
            "volume":  nq.volume,
        }
        for t, nq in quotes.items()
    }


# ---------------------------------------------------------------------------
# GET /watchlist/export
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_watchlist(db: asyncpg.Connection = Depends(get_db)):
    """Export all watchlist tickers in CSV format."""
    csv_data = await export_watchlist_to_csv(db)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=watchlist_export.csv"}
    )


# ---------------------------------------------------------------------------
# POST /watchlist/import
# ---------------------------------------------------------------------------

@router.post("/import")
async def import_watchlist(
    file: UploadFile = File(...),
    db: asyncpg.Connection = Depends(get_db)
):
    """Import tickers from a CSV file."""
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")

    inserted, updated = await import_watchlist_from_csv(db, csv_text)
    return {"inserted": inserted, "updated": updated}

