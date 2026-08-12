"""
services/sector_strength_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sector relative-strength vs SPY benchmark.

Fetches live quotes for 11 GICS sector SPDR ETFs + SPY, computes
intraday RS = ETF_chg% − SPY_chg%, and classifies each sector as
leading / inline / lagging.  Aggregates into an overall market tone.

The ``SECTOR_ETFS`` dict is the default basket; callers can pass
``sector_etfs`` overrides to customise the mapping at runtime.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

SECTOR_ETFS: Dict[str, str] = {
    "Technology":       "XLK",
    "Healthcare":       "XLV",
    "Financials":       "XLF",
    "Consumer Disc.":   "XLY",
    "Industrials":      "XLI",
    "Energy":           "XLE",
    "Materials":        "XLB",
    "Communication":    "XLC",
    "Consumer Staples": "XLP",
    "Real Estate":      "XLRE",
    "Utilities":        "XLU",
}
BENCHMARK = "SPY"

def market_tone_label(leading_count: int, lagging_count: int, total: int) -> str:
    if leading_count >= 7:
        return "bullish"
    elif lagging_count >= 7:
        return "bearish"
    elif leading_count >= 4 and lagging_count >= 4:
        return "rotation"
    return "mixed"

async def build_sector_strength(
    get_live_quotes_fn,
    *,
    polygon_api_key: Optional[str] = None,
    sector_etfs: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    active_etfs = SECTOR_ETFS.copy()
    if sector_etfs:
        active_etfs.update(sector_etfs)

    tickers = list(active_etfs.values()) + [BENCHMARK]
    quotes = await get_live_quotes_fn(tickers, polygon_api_key=polygon_api_key)

    spy_quote = quotes.get(BENCHMARK)
    if not spy_quote or spy_quote.last_price is None or spy_quote.change_pct is None:
        return {
            "spy": None,
            "sectors": [],
            "leading_count": 0,
            "lagging_count": 0,
            "market_tone": "mixed",
            "benchmark": BENCHMARK,
            "error": "Failed to fetch SPY benchmark quote",
        }

    spy_chg_pct = spy_quote.change_pct
    spy_price = spy_quote.last_price

    sectors = []
    leading_count = 0
    lagging_count = 0

    for sector, etf in active_etfs.items():
        q = quotes.get(etf)
        if not q or q.last_price is None or q.change_pct is None:
            continue

        etf_price = q.last_price
        etf_chg = q.change_pct
        rs_vs_spy = etf_chg - spy_chg_pct

        status = "inline"
        if rs_vs_spy > 0.25:
            status = "leading"
            leading_count += 1
        elif rs_vs_spy < -0.25:
            status = "lagging"
            lagging_count += 1

        sectors.append({
            "sector": sector,
            "etf": etf,
            "price": round(etf_price, 2),
            "chg_pct": round(etf_chg, 2),
            "rs_vs_spy": round(rs_vs_spy, 2),
            "status": status,
        })

    sectors.sort(key=lambda x: x["rs_vs_spy"], reverse=True)
    total_sectors = len(sectors)

    return {
        "spy": {"price": spy_price, "chg_pct": spy_chg_pct},
        "sectors": sectors,
        "leading_count": leading_count,
        "lagging_count": lagging_count,
        "market_tone": market_tone_label(leading_count, lagging_count, total_sectors),
        "benchmark": BENCHMARK,
    }
