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
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..db import get_db, rows_to_list, row_to_dict
from validation.schemas import WatchlistAddBody, WatchlistUpdateBody

log = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist", tags=["watchlist"])


# ---------------------------------------------------------------------------
# GET /watchlist
# ---------------------------------------------------------------------------

@router.get("")
async def list_watchlist(db: asyncpg.Connection = Depends(get_db)):
    """Return all watchlist tickers ordered by last viewed / added."""
    rows = await db.fetch(
        "SELECT * FROM watchlist ORDER BY last_viewed_at DESC NULLS LAST, added_at DESC"
    )
    return rows_to_list(rows)


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

    tags = json.dumps([str(t).strip() for t in tags_raw if str(t).strip()])
    now  = datetime.now(timezone.utc)

    try:
        await db.execute(
            "INSERT INTO watchlist (ticker, sector, notes, tags, added_at) VALUES ($1, $2, $3, $4, $5)",
            ticker, sector, notes, tags, now,
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
    ticker = ticker.upper().strip()
    row = await db.fetchrow("SELECT ticker FROM watchlist WHERE ticker = $1", ticker)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    updates: dict = {}
    if data.notes is not None:
        updates["notes"] = data.notes
    if data.sector is not None:
        updates["sector"] = data.sector
    if data.tags is not None:
        updates["tags"] = json.dumps(data.tags)

    set_parts = [f"{k} = ${i+1}" for i, k in enumerate(updates)]
    values    = list(updates.values()) + [ticker]
    await db.execute(
        f"UPDATE watchlist SET {', '.join(set_parts)} WHERE ticker = ${len(values)}",
        *values,
    )
    return {"success": True}


# ---------------------------------------------------------------------------
# POST /watchlist/{ticker}/viewed
# ---------------------------------------------------------------------------

@router.post("/{ticker}/viewed")
async def mark_viewed(ticker: str, db: asyncpg.Connection = Depends(get_db)):
    ticker = ticker.upper().strip()
    now = datetime.now(timezone.utc)
    await db.execute(
        "UPDATE watchlist SET last_viewed_at = $1 WHERE ticker = $2", now, ticker
    )
    return {"success": True}


# ---------------------------------------------------------------------------
# DELETE /watchlist/{ticker}
# ---------------------------------------------------------------------------

@router.delete("/{ticker}")
async def remove_from_watchlist(ticker: str, db: asyncpg.Connection = Depends(get_db)):
    ticker = ticker.upper().strip()
    row = await db.fetchrow("SELECT ticker FROM watchlist WHERE ticker = $1", ticker)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await db.execute("DELETE FROM watchlist WHERE ticker = $1", ticker)
    return {"success": True}


# ---------------------------------------------------------------------------
# GET /watchlist/prices
# ---------------------------------------------------------------------------

@router.get("/prices")
async def watchlist_prices(db: asyncpg.Connection = Depends(get_db)):
    """Return Schwab (or Polygon fallback) price + % change for every watchlist ticker in batch."""
    rows = await db.fetch("SELECT ticker FROM watchlist ORDER BY added_at DESC")
    tickers = [r["ticker"] for r in rows]
    if not tickers:
        return {}

    results = {}
    try:
        from services.schwab_client import get_quotes
        quotes = await asyncio.to_thread(get_quotes, list(tickers))
        for t in tickers:
            q_data = quotes.get(t, {})
            quote = q_data.get('quote', {}) if q_data else {}
            results[t] = {
                "price": quote.get("lastPrice"),
                "chg_pct": quote.get("netPercentChange"),
                "volume": quote.get("totalVolume")
            }
    except Exception as e:
        log.warning(f"Failed to fetch Schwab quotes for watchlist: {e}")
        polygon_key = settings.polygon_api_key
        if polygon_key:
            def _fetch_polygon_prices() -> dict:
                import requests as _req
                poly_results = {}
                for t in tickers:
                    try:
                        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{t}"
                        resp = _req.get(url, params={"apiKey": polygon_key}, timeout=5)
                        if resp.ok:
                            snap = resp.json().get("ticker", {})
                            day = snap.get("day", {})
                            prev = snap.get("prevDay", {})
                            price = day.get("c") or snap.get("last", {}).get("price")
                            prev_c = prev.get("c")
                            chg_pct = round((price - prev_c) / prev_c * 100, 2) if price and prev_c else None
                            poly_results[t] = {"price": price, "chg_pct": chg_pct, "volume": day.get("v")}
                    except Exception:
                        poly_results[t] = {"price": None, "chg_pct": None, "volume": None}
                return poly_results
            results = await asyncio.to_thread(_fetch_polygon_prices)
        else:
            for t in tickers:
                results[t] = {"price": None, "chg_pct": None, "volume": None}

    return results
