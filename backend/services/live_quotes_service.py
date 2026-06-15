"""
services/live_quotes_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Single function: batch-fetch live quotes for many tickers with
Schwab as primary source and Polygon as per-ticker fallback.

Replaces inline implementations in 4 routers:
  - routers/continuation.py:54-72
  - routers/watchlist.py:170-204
  - routers/gainers.py:500-531
  - routers/market.py:77-125

Each of those previously did its own:
  1. `await asyncio.to_thread(get_quotes, list(tickers))` against Schwab.
  2. Optional Polygon fallback (raw requests loop, or non-functional
     `get_ticker_snapshot` shim that just re-calls Schwab).
  3. Unwrap of `quotes[t].get('quote', {}).get('lastPrice')`.

Public surface:

    NormalizedQuote              # dataclass, snake_case fields
    get_live_quotes(tickers,
                    polygon_api_key=None) -> dict[ticker, NormalizedQuote]

Originally extracted as RFC-004 QW-1 (handoff #014).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path bootstrap: keep `services.*` importable when this module is loaded
# from a router context (mirrors chart_data_service.py pattern).
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_THIS_DIR)
for _p in (_THIS_DIR, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NormalizedQuote:
    """Ticker-agnostic live quote. All numeric fields Optional.

    Fields:
        ticker:     Echo of input symbol (case-preserved from caller).
        last_price: Current/most-recent trade price.
        open_price: Session open price.
        volume:     Cumulative session volume (int when known).
        change_pct: Net % change for the session, already in percent units
                    (matches Schwab's `netPercentChange`, not 0.085).
        prev_close: Previous regular-session close. Populated by both
                    sources; used to derive `change_pct` on Polygon path.
        source:     "schwab" | "polygon" | "none".
    """
    ticker: str
    last_price: Optional[float] = None
    open_price: Optional[float] = None
    volume: Optional[int] = None
    change_pct: Optional[float] = None
    prev_close: Optional[float] = None
    source: str = "none"

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Shape unwrappers (pure helpers, unit-testable in isolation)
# ---------------------------------------------------------------------------

def _quote_from_schwab(ticker: str, payload: Optional[dict]) -> Optional[NormalizedQuote]:
    """Unwrap one entry of `schwab_client.get_quotes()` output.

    Input shape (per ticker):
        {"quote": {"lastPrice": .., "openPrice": .., "totalVolume": ..,
                   "netPercentChange": .., "closePrice": ..}}

    Returns None if the entry is missing, empty, or has no lastPrice
    (Schwab returns entries with `None` lastPrice for halted/OTC symbols).
    """
    quote = (payload or {}).get("quote") or {}
    last = quote.get("lastPrice")
    if last is None:
        return None
    return NormalizedQuote(
        ticker=ticker,
        last_price=last,
        open_price=quote.get("openPrice"),
        volume=quote.get("totalVolume"),
        change_pct=quote.get("netPercentChange"),
        prev_close=quote.get("closePrice"),
        source="schwab",
    )


def _quote_from_polygon(ticker: str, snap: Optional[dict]) -> Optional[NormalizedQuote]:
    """Unwrap a Polygon `/v2/snapshot/.../tickers/{t}` JSON body.

    Expected shape (single-ticker endpoint):
        {"ticker": {"day":   {"o":.., "h":.., "l":.., "c":.., "v":..},
                    "prevDay": {"c":.., "v":..},
                    "last": {"p":..}}}

    Falls back to top-level dict for endpoints that omit the 'ticker'
    wrapper. Returns None if no last price is recoverable.
    """
    if not isinstance(snap, dict):
        return None
    inner = snap.get("ticker", snap)
    if not isinstance(inner, dict):
        return None
    day = inner.get("day") or {}
    prev = inner.get("prevDay") or {}
    last_trade = inner.get("last") or {}
    last = day.get("c") or last_trade.get("price")
    if last is None:
        return None
    prev_close = prev.get("c")
    change_pct = None
    if last and prev_close:
        change_pct = round((last - prev_close) / prev_close * 100, 2)
    raw_vol = day.get("v")
    try:
        vol_int: Optional[int] = int(raw_vol) if raw_vol is not None else None
    except (TypeError, ValueError):
        vol_int = None
    return NormalizedQuote(
        ticker=ticker,
        last_price=last,
        open_price=day.get("o"),
        volume=vol_int,
        change_pct=change_pct,
        prev_close=prev_close,
        source="polygon",
    )


# ---------------------------------------------------------------------------
# Polygon REST adapter (synchronous; runs in threadpool via to_thread)
# ---------------------------------------------------------------------------

def _polygon_fetch_one_sync(ticker: str, api_key: str) -> Optional[dict]:
    """Block on a single Polygon snapshot GET. Returns parsed JSON or None.

    Failures (timeout, 4xx, 5xx, missing lib) all yield None — callers
    treat None as "no data for this ticker" and leave the NormalizedQuote
    empty. We never raise: quote-fetching should never take down a route.
    """
    try:
        import requests as _req
    except ImportError:
        log.warning("[live_quotes] 'requests' not installed; Polygon fallback disabled")
        return None
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        resp = _req.get(url, params={"apiKey": api_key}, timeout=5)
        if not resp.ok:
            log.warning("[live_quotes] Polygon snapshot %s: HTTP %s", ticker, resp.status_code)
            return None
        return resp.json()
    except Exception as exc:
        log.warning("[live_quotes] Polygon snapshot %s failed: %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_live_quotes(
    tickers: List[str],
    *,
    polygon_api_key: Optional[str] = None,
) -> Dict[str, NormalizedQuote]:
    """Fetch live quotes for `tickers` with Schwab primary, Polygon fallback.

    Every requested ticker is present in the returned dict. Missing or
    empty data yields a NormalizedQuote with `source="none"` and all
    numeric fields set to None — callers can `result[t].last_price` without
    KeyError or null guards.

    Args:
        tickers: List of symbols. De-duplicated, order-preserving, case
            of the first occurrence wins.
        polygon_api_key: Polygon API key for the per-ticker fallback path.
            If None or empty, no Polygon calls are made and missing tickers
            remain `source="none"`.

    Returns:
        dict[ticker, NormalizedQuote]. Keys are the caller-supplied tickers
        (first-seen casing), not the response-supplied ones.
    """
    unique: List[str] = []
    seen_upper: set = set()
    for t in tickers or []:
        if not t:
            continue
        upper = t.upper()
        if upper in seen_upper:
            continue
        seen_upper.add(upper)
        unique.append(t)
    if not unique:
        return {}

    results: Dict[str, NormalizedQuote] = {
        t: NormalizedQuote(ticker=t) for t in unique
    }

    # 1. Schwab batch (primary) — chunked internally by schwab-py.
    try:
        from services.schwab_client import get_quotes
        schwab_payload = await asyncio.to_thread(get_quotes, unique)
    except Exception as exc:
        log.warning("[live_quotes] Schwab get_quotes failed: %s", exc)
        schwab_payload = {}

    missing: List[str] = []
    for t in unique:
        nq = _quote_from_schwab(t, schwab_payload.get(t, {}))
        if nq is not None:
            results[t] = nq
        else:
            missing.append(t)

    # 2. Polygon per-ticker fallback (only for tickers Schwab didn't return).
    if missing and polygon_api_key:
        async def _one(t: str) -> None:
            snap = await asyncio.to_thread(_polygon_fetch_one_sync, t, polygon_api_key)
            nq = _quote_from_polygon(t, snap) if snap else None
            if nq is not None:
                results[t] = nq
        await asyncio.gather(*(_one(t) for t in missing))

    return results
