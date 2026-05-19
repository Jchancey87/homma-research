"""
fastapi_app/routers/market.py
Async port of backend/routes/market.py.

Routes:
  GET /market/breadth   — SPY/QQQ/IWM live prices (cached 15 min in-process)
  GET /market/calendar  — Economic events this week via FMP (cached 6 h)
"""
from __future__ import annotations

import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter

from ..config import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])

# ---------------------------------------------------------------------------
# In-process caches (mirrors Flask implementation — replaced with Redis later)
# ---------------------------------------------------------------------------

_breadth_cache: dict = {"data": None, "fetched_at": 0}
_breadth_lock = asyncio.Lock()
BREADTH_TTL = 15 * 60  # 15 minutes

_calendar_cache: dict = {"data": None, "fetched_at": 0}
_calendar_lock = asyncio.Lock()
CALENDAR_TTL = 6 * 60 * 60  # 6 hours

INDICES = ["SPY", "QQQ", "IWM"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bias_label(spy_chg: Optional[float], vix: Optional[float]) -> str:
    """Derive a simple risk-on / risk-off bias label."""
    if spy_chg is None:
        return "unknown"
    if spy_chg >= 0.5 and (vix is None or vix < 20):
        return "risk_on"
    if spy_chg <= -0.5 or (vix is not None and vix > 25):
        return "risk_off"
    return "neutral"


# ---------------------------------------------------------------------------
# GET /market/breadth
# ---------------------------------------------------------------------------

@router.get("/breadth")
async def market_breadth():
    """
    Live index prices for SPY, QQQ, IWM — cached for 15 minutes.
    Returns per-index price + % change, plus a derived bias label.
    """
    async with _breadth_lock:
        now = time.time()
        if _breadth_cache["data"] and (now - _breadth_cache["fetched_at"]) < BREADTH_TTL:
            return _breadth_cache["data"]

    indices: dict = {}
    spy_chg: Optional[float] = None
    vix: Optional[float] = None

    # Delegate to existing polygon/Schwab shim — runs in a thread to avoid
    # blocking the event loop (the shim is still sync).
    for ticker in INDICES:
        try:
            snap = await asyncio.to_thread(_fetch_snapshot_sync, ticker)
        except Exception as exc:
            log.warning("[market] Snapshot error for %s: %s", ticker, exc)
            snap = None

        if snap:
            close  = _extract_close(snap)
            prev_c = _extract_prev_close(snap)
            volume = _extract_volume(snap)
            chg_pct = round((close - prev_c) / prev_c * 100, 2) if close and prev_c else None
            if ticker == "SPY":
                spy_chg = chg_pct
            indices[ticker] = {
                "ticker":  ticker,
                "price":   close,
                "chg_pct": chg_pct,
                "volume":  volume,
            }

    data = {
        "indices":    indices,
        "vix":        vix,
        "bias":       _bias_label(spy_chg, vix),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cache_ttl_s": BREADTH_TTL,
    }

    async with _breadth_lock:
        _breadth_cache["data"] = data
        _breadth_cache["fetched_at"] = time.time()

    return data


def _fetch_snapshot_sync(ticker: str):
    """Synchronous shim call — runs in threadpool via asyncio.to_thread()."""
    import sys, os
    _backend = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if _backend not in sys.path:
        sys.path.insert(0, _backend)
    from services.polygon_client import get_ticker_snapshot
    return get_ticker_snapshot(ticker)


def _extract_close(snap) -> Optional[float]:
    if isinstance(snap, dict):
        day = snap.get("day", {})
        return day.get("c") or snap.get("last", {}).get("price")
    if hasattr(snap, "last_trade") and snap.last_trade:
        return snap.last_trade.price
    return getattr(snap, "close", None)


def _extract_prev_close(snap) -> Optional[float]:
    if isinstance(snap, dict):
        return snap.get("prevDay", {}).get("c")
    prev = getattr(snap, "prev_day", None)
    return getattr(prev, "close", None) if prev else None


def _extract_volume(snap) -> Optional[float]:
    if isinstance(snap, dict):
        return snap.get("day", {}).get("v")
    day = getattr(snap, "day", None)
    if day is None:
        return None
    return getattr(day, "v", None)


# ---------------------------------------------------------------------------
# GET /market/calendar
# ---------------------------------------------------------------------------

@router.get("/calendar")
async def economic_calendar():
    """
    Economic events for the next 7 days via FMP.
    Cached for 6 hours to preserve FMP quota.
    """
    async with _calendar_lock:
        now = time.time()
        if _calendar_cache["data"] and (now - _calendar_cache["fetched_at"]) < CALENDAR_TTL:
            return _calendar_cache["data"]

    fmp_key = settings.fmp_api_key
    if not fmp_key:
        return {"events": [], "source": "fmp_key_missing"}

    today = datetime.utcnow().date()
    end   = (today + timedelta(days=7)).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(
                "https://financialmodelingprep.com/api/v3/economic_calendar",
                params={"from": today.isoformat(), "to": end, "apikey": fmp_key},
            )
            resp.raise_for_status()
            raw = resp.json()

        events = []
        for e in (raw or []):
            impact = (e.get("impact") or "").lower()
            if impact not in ("high", "medium"):
                continue
            events.append({
                "date":     e.get("date", "")[:10],
                "time":     e.get("date", "")[11:16],
                "event":    e.get("event"),
                "country":  e.get("country"),
                "impact":   impact,
                "actual":   e.get("actual"),
                "estimate": e.get("estimate"),
                "previous": e.get("previous"),
            })

        events.sort(key=lambda x: x["date"])
        data = {"events": events, "source": "fmp", "fetched_at": today.isoformat()}

    except Exception as exc:
        log.warning("[market] FMP calendar error: %s", exc)
        data = {"events": [], "source": "fmp_error", "error": str(exc)}

    async with _calendar_lock:
        _calendar_cache["data"] = data
        _calendar_cache["fetched_at"] = time.time()

    return data
