"""
fastapi_app/routers/chart.py
Lightweight read-only endpoints derived from the live screener cache.

Kept as its own router (prefix=/chart) so the /api/chart/* path
stays stable even as the gainers/screener internals evolve.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)
router = APIRouter(prefix="/chart", tags=["chart"])


# Hard cap on tickers per request — protects the upstream Schwab quote
# fan-out when many charts request prices concurrently.
MAX_TICKERS_PER_REQUEST = 50


# ---------------------------------------------------------------------------
# GET /chart/live-price
# ---------------------------------------------------------------------------

@router.get("/live-price")
async def chart_live_price(
    tickers: Optional[str] = Query(
        None,
        description="Comma-separated ticker symbols (max 50). Empty/missing returns empty map.",
    ),
):
    """
    Return the last traded price for each requested ticker, sourced from the
    in-memory live screener cache (refreshed every 60s by the background
    refresh loop). Tickers not present in the cache are returned as null.
    """
    raw = (tickers or "").strip()
    if not raw:
        return {"prices": {}}

    requested = [t.strip().upper() for t in raw.split(",") if t.strip()]
    # Dedupe while preserving order so the response shape is stable.
    seen = set()
    ordered: list[str] = []
    for t in requested:
        if t and t not in seen:
            seen.add(t)
            ordered.append(t)

    if len(ordered) > MAX_TICKERS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many tickers: {len(ordered)} > max {MAX_TICKERS_PER_REQUEST}",
        )

    from services.live_screener import get_live_gainers

    def _fetch_prices_map() -> dict[str, Optional[float]]:
        snap = get_live_gainers()
        return {
            g["ticker"]: g.get("last_price")
            for g in snap.get("gainers", [])
            if g.get("ticker")
        }

    prices_by_ticker = await asyncio.to_thread(_fetch_prices_map)

    prices = {t: prices_by_ticker.get(t) for t in ordered}
    return {"prices": prices}
