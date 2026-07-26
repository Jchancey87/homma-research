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
