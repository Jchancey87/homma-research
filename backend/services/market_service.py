"""
Market Service.

Business logic for market breadth, regime calculations, VIX parsing, and economic calendar fetching.
Follows RFC-001 thin router rules.
"""

import math
import time
import logging
from typing import Dict, List, Optional
from validation import EASTERN_TZ

log = logging.getLogger(__name__)

INDICES = ["SPY", "QQQ", "IWM"]
BREADTH_TTL = 15 * 60
CALENDAR_TTL = 6 * 60 * 60


def bias_label(spy_chg: Optional[float], vix: Optional[float]) -> str:
    if spy_chg is None:
        return "unknown"
    if spy_chg >= 0.5 and (vix is None or vix < 20):
        return "risk_on"
    if spy_chg <= -0.5 or (vix is not None and vix > 25):
        return "risk_off"
    return "neutral"


def clean_nans(obj):
    if isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(x) for x in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


async def fetch_breadth_data(quotes_map: dict) -> dict:
    indices: dict = {}
    spy_chg: Optional[float] = None
    vix: Optional[float] = None

    for ticker in INDICES:
        nq = quotes_map.get(ticker)
        if nq is None or nq.last_price is None:
            continue
        if ticker == "SPY":
            spy_chg = nq.change_pct
        indices[ticker] = {
            "ticker": ticker,
            "price": nq.last_price,
            "chg_pct": nq.change_pct,
            "volume": nq.volume,
        }

    vix_q = quotes_map.get("$VIX") or quotes_map.get("VIX")
    if vix_q and vix_q.last_price:
        vix = vix_q.last_price

    return {
        "indices": indices,
        "vix": vix,
        "bias": bias_label(spy_chg, vix),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cache_ttl_s": BREADTH_TTL,
    }


# In-memory store for active MTF scanner items
_mtf_scanner_cache: dict = {"timestamp": None, "in_play": []}


def set_mtf_scanner_state(in_play_items: list):
    """Update active MTF scanner items from background streaming task or dynamic scan."""
    _mtf_scanner_cache["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _mtf_scanner_cache["in_play"] = in_play_items


async def get_mtf_scanner_state(
    min_price: float = 1.0,
    max_price: float = 20.0,
    min_rvol: float = 5.0,
    max_float: Optional[float] = 20_000_000,
    min_score: int = 50,
    coincident_only: bool = False,
    sort_by: str = "score",
    force_refresh: bool = False,
) -> dict:
    """Retrieve active MTF scanner state with customizable momentum/confluence filters."""
    from services.mtf_sr_service import filter_mtf_candidates, scan_mtf_market_candidates

    raw_items = _mtf_scanner_cache.get("in_play", [])

    # If cache is empty or force_refresh requested, scan candidates dynamically
    if not raw_items or force_refresh:
        try:
            scanned = scan_mtf_market_candidates(limit=60)
            if scanned:
                set_mtf_scanner_state(scanned)
                raw_items = scanned
        except Exception as e:
            log.warning("Dynamic MTF market candidate scan failed: %s", e)

    filtered_items = filter_mtf_candidates(
        raw_items,
        min_price=min_price,
        max_price=max_price,
        min_rvol=min_rvol,
        max_float=max_float,
        min_score=min_score,
        coincident_only=coincident_only,
        sort_by=sort_by,
    )

    return {
        "timestamp": _mtf_scanner_cache.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "filters_applied": {
            "min_price": min_price,
            "max_price": max_price,
            "min_rvol": min_rvol,
            "max_float": max_float,
            "min_score": min_score,
            "coincident_only": coincident_only,
            "sort_by": sort_by,
        },
        "total_scanned": len(raw_items),
        "total_in_play": len(filtered_items),
        "in_play": filtered_items,
    }


