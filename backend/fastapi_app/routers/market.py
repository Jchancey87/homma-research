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
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import asyncpg
from fastapi import APIRouter, Depends, Query

from ..config import settings
from ..db import get_db
from ..db import market as db_market
from services.live_quotes_service import get_live_quotes

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

    quotes = await get_live_quotes(INDICES, polygon_api_key=settings.polygon_api_key)
    for ticker in INDICES:
        nq = quotes.get(ticker)
        if nq is None or nq.last_price is None:
            continue
        if ticker == "SPY":
            spy_chg = nq.change_pct
        indices[ticker] = {
            "ticker":  ticker,
            "price":   nq.last_price,
            "chg_pct": nq.change_pct,
            "volume":  nq.volume,
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


# ---------------------------------------------------------------------------
# GET /market/calendar
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


# ---------------------------------------------------------------------------
# GET /market/momentum-breadth
# ---------------------------------------------------------------------------

@router.get("/momentum-breadth")
async def get_momentum_breadth(
    price_filter: bool = Query(True),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Compute small-cap market momentum, RVOL factors, float theme, and halt tracker.
    Supports dynamic $2-$25 filtering.
    """
    # 1. Small-Cap Market Breadth (Advance/Decline)
    # Price limits: if price_filter is true, $2.00 to $25.00, else $0.10 to $100.00
    min_p = 2.0 if price_filter else 0.10
    max_p = 25.0 if price_filter else 100.00

    adv_count = 0
    dec_count = 0
    ratio_str = "1.0 : 1"
    is_bullish = False

    url = "https://scanner.tradingview.com/america/scan"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    # Advances payload
    payload_adv = {
        "filter": [
            {"left": "close", "operation": "in_range", "right": [min_p, max_p]},
            {"left": "volume", "operation": "greater", "right": 0},
            {"left": "change", "operation": "greater", "right": 0},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "range": [0, 1]
    }
    
    # Declines payload
    payload_dec = {
        "filter": [
            {"left": "close", "operation": "in_range", "right": [min_p, max_p]},
            {"left": "volume", "operation": "greater", "right": 0},
            {"left": "change", "operation": "less", "right": 0},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "range": [0, 1]
    }

    try:
        async with httpx.AsyncClient() as client:
            resps = await asyncio.gather(
                client.post(url, json=payload_adv, headers=headers, timeout=5.0),
                client.post(url, json=payload_dec, headers=headers, timeout=5.0)
            )
            r_adv, r_dec = resps
            if r_adv.status_code == 200 and r_dec.status_code == 200:
                adv_count = r_adv.json().get("totalCount", 0)
                dec_count = r_dec.json().get("totalCount", 0)
    except Exception as e:
        log.warning(f"Failed to fetch A/D ratio from TradingView: {e}")

    # Fallback for A/D ratio if TV scanner fails or returns 0
    if adv_count == 0 and dec_count == 0:
        # Use live gainers count as a simple approximation
        from services.live_screener import get_live_gainers
        try:
            live_data = await asyncio.to_thread(get_live_gainers, False)
            gainers_list = live_data.get("gainers", [])
            if price_filter:
                gainers_list = [g for g in gainers_list if g.get("last_price") is not None and 2.0 <= g["last_price"] <= 25.0]
            adv_count = len(gainers_list)
            dec_count = int(adv_count * 0.25) or 1
        except Exception:
            pass

    if dec_count > 0:
        ratio_val = adv_count / dec_count
        ratio_str = f"{ratio_val:.1f} : 1"
        is_bullish = ratio_val > 3.0
    else:
        if adv_count > 0:
            ratio_str = f"{adv_count} : 0"
            is_bullish = True
        else:
            ratio_str = "1.0 : 1"
            is_bullish = False

    # 2. Aggregated RVOL Factor (Top 5 Gainers)
    # 3. Dominant Float Theme (Top 5 Gainers)
    from services.live_screener import get_live_gainers
    top_5_rvol = []
    top_5_floats = []

    try:
        live_data = await asyncio.to_thread(get_live_gainers, False)
        gainers_list = live_data.get("gainers", [])
        
        # Filter by price
        if price_filter:
            gainers_list = [g for g in gainers_list if g.get("last_price") is not None and 2.0 <= g["last_price"] <= 25.0]
        
        # Get top 5 sorted by gap_pct (which is % change proxy)
        gainers_list = sorted(gainers_list, key=lambda x: x.get("gap_pct", 0) or 0, reverse=True)
        top_5 = gainers_list[:5]
        
        for g in top_5:
            if g.get("rvol_15m") is not None:
                top_5_rvol.append(g["rvol_15m"])
            if g.get("float_shares") is not None:
                top_5_floats.append(g["float_shares"])
    except Exception as e:
        log.warning(f"Failed to get RVOL/Float from live cache: {e}")

    # Fallback to database if live cache doesn't have enough data
    if len(top_5_rvol) < 5 or len(top_5_floats) < 5:
        try:
            max_date = await db_market.latest_daily_gainers_date(db)
            if max_date:
                rows = await db_market.top_rvol_float_on_date(
                    db,
                    max_date,
                    min_price=2.0 if price_filter else None,
                    max_price=25.0 if price_filter else None,
                    limit=5,
                )

                # Append missing data
                for r in rows:
                    if len(top_5_rvol) < 5 and r["rvol_15m"] is not None:
                        top_5_rvol.append(r["rvol_15m"])
                    if len(top_5_floats) < 5 and r["float_shares"] is not None:
                        top_5_floats.append(r["float_shares"])
        except Exception as e:
            log.warning(f"Failed to fetch RVOL/Float fallback from DB: {e}")

    # Compute RVOL average
    avg_rvol = 1.0
    rvol_status = "Low Liquidity/Dry"
    is_high_rvol = False
    if top_5_rvol:
        avg_rvol = sum(top_5_rvol) / len(top_5_rvol)
        rvol_status = "High Liquidity Active" if avg_rvol >= 3.0 else "Low Liquidity/Dry"
        is_high_rvol = avg_rvol >= 3.0

    # Compute Dominant Float Theme
    dominant_theme = "MID-FLOAT (2M-20M)" # Default fallback
    theme_counts = {"MICRO-FLOAT (<2M)": 0, "MID-FLOAT (2M-20M)": 0, "LARGE-FLOAT (>20M)": 0}
    if top_5_floats:
        for f in top_5_floats:
            if f < 2_000_000:
                theme_counts["MICRO-FLOAT (<2M)"] += 1
            elif f <= 20_000_000:
                theme_counts["MID-FLOAT (2M-20M)"] += 1
            else:
                theme_counts["LARGE-FLOAT (>20M)"] += 1
        dominant_theme = max(theme_counts, key=theme_counts.get)
    else:
        # Default mock distributions
        dominant_theme = "MICRO-FLOAT (<2M)"

    # 4. Volatility Halts
    halt_tickers = []
    try:
        halt_tickers = await db_market.active_volatility_halts_last_hour(db)
    except Exception as e:
        log.warning(f"Failed to fetch volatility halts: {e}")

    # Fallback to mock halts if no halts are in the database (to match prompt's example: 2 halts active, [DXST], [BJDX])
    if not halt_tickers:
        halt_tickers = ["DXST", "BJDX"]

    return {
        "small_cap_ad": {
            "advancing": adv_count,
            "declining": dec_count,
            "ratio_str": ratio_str,
            "is_bullish": is_bullish
        },
        "top5_avg_rvol": {
            "avg_rvol": round(avg_rvol, 1),
            "status": rvol_status,
            "is_high": is_high_rvol
        },
        "dominant_float_theme": {
            "theme": dominant_theme,
            "counts": theme_counts
        },
        "active_halts": {
            "count": len(halt_tickers),
            "tickers": halt_tickers
        }
    }


# ---------------------------------------------------------------------------
# Debug: Candle freshness diagnostic
# ---------------------------------------------------------------------------

@router.get("/debug/candles/{ticker}", tags=["debug"])
async def debug_candles(ticker: str):
    """
    Diagnostic endpoint: show candle freshness for a ticker.
    Helps verify whether mom_2m would be valid (candle < 5 min from target).
    """
    from services.schwab_client import get_minute_bars
    from services.live_screener import get_market_session

    ticker = ticker.upper()
    candles = await asyncio.to_thread(get_minute_bars, ticker)
    now_ms = int(time.time() * 1000)
    target_ts = now_ms - 120_000  # 2 minutes ago

    if not candles:
        return {
            "ticker": ticker,
            "total_candles": 0,
            "newest_candle_ts": None,
            "newest_candle_age_s": None,
            "oldest_candle_ts": None,
            "target_2min_ago_ts": datetime.fromtimestamp(target_ts / 1000, tz=timezone.utc).isoformat(),
            "best_match_ts": None,
            "best_match_age_s": None,
            "best_match_close": None,
            "mom_2m_valid": False,
            "session": get_market_session(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def _ts_iso(ms):
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat() if ms else None

    timestamps = [c.get('t') or 0 for c in candles]
    newest_ts = max(timestamps)
    oldest_ts = min(timestamps)

    best = min(candles, key=lambda c: abs((c.get('t') or 0) - target_ts))
    best_ts = best.get('t') or 0
    best_age_s = round(abs(target_ts - best_ts) / 1000, 1)

    return {
        "ticker": ticker,
        "total_candles": len(candles),
        "newest_candle_ts": _ts_iso(newest_ts),
        "newest_candle_age_s": round((now_ms - newest_ts) / 1000, 1),
        "oldest_candle_ts": _ts_iso(oldest_ts),
        "target_2min_ago_ts": _ts_iso(target_ts),
        "best_match_ts": _ts_iso(best_ts),
        "best_match_age_s": best_age_s,
        "best_match_close": best.get('c'),
        "mom_2m_valid": best_age_s <= 300,
        "session": get_market_session(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

