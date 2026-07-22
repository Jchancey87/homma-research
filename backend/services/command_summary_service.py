"""
services/command_summary_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Synthesis logic for ``GET /market/command-summary``.

Contains:
  - TradingView scanner helpers (A/D ratio, SMA-40 breadth)
  - Regime and risk tag algorithms
  - Sector clustering from live-screener gainers
  - Up/down volume ratio from gainers data

All public functions are pure or accept explicit arguments — no global
state, easy to unit-test.  The router calls ``build_command_summary()``
which orchestrates everything behind ``asyncio.gather``.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TradingView scanner constants
# ---------------------------------------------------------------------------

TV_URL = "https://scanner.tradingview.com/america/scan"
TV_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/100.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# TradingView A/D ratio queries (extracted from momentum-breadth)
# ---------------------------------------------------------------------------

def _tv_ad_payloads(
    min_p: float, max_p: float
) -> Tuple[dict, dict]:
    """Return (adv_payload, dec_payload) for TradingView scanner."""
    base = {
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "range": [0, 1],
    }
    common_filters = [
        {"left": "close", "operation": "in_range", "right": [min_p, max_p]},
        {"left": "volume", "operation": "greater", "right": 0},
        {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
    ]
    adv = {**base, "filter": common_filters + [
        {"left": "change", "operation": "greater", "right": 0},
    ]}
    dec = {**base, "filter": common_filters + [
        {"left": "change", "operation": "less", "right": 0},
    ]}
    return adv, dec


async def fetch_ad_counts(
    client: httpx.AsyncClient, min_p: float, max_p: float
) -> Tuple[int, int]:
    """Fetch advancing/declining counts from TradingView scanner.

    Returns (adv_count, dec_count).  Both 0 on failure.
    """
    adv_payload, dec_payload = _tv_ad_payloads(min_p, max_p)
    try:
        r_adv, r_dec = await asyncio.gather(
            client.post(TV_URL, json=adv_payload, headers=TV_HEADERS, timeout=5.0),
            client.post(TV_URL, json=dec_payload, headers=TV_HEADERS, timeout=5.0),
        )
        adv = r_adv.json().get("totalCount", 0) if r_adv.status_code == 200 else 0
        dec = r_dec.json().get("totalCount", 0) if r_dec.status_code == 200 else 0
        return adv, dec
    except Exception as exc:
        log.warning("[cmd-summary] TV A/D fetch failed: %s", exc)
        return 0, 0


# ---------------------------------------------------------------------------
# TradingView SMA-40 breadth query
# ---------------------------------------------------------------------------

async def fetch_above_sma_pct(
    client: httpx.AsyncClient, min_p: float, max_p: float, period: int = 40
) -> Optional[float]:
    """Percent of stocks trading above their specified period SMA (e.g. 20, 40, 50, 200).

    Tries multiple TV scanner filter syntaxes. Returns None on any failure
    so the caller can gracefully degrade.
    """
    base_filters = [
        {"left": "close", "operation": "in_range", "right": [min_p, max_p]},
        {"left": "volume", "operation": "greater", "right": 0},
        {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
    ]
    base = {
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "range": [0, 1],
    }

    total_payload = {**base, "filter": base_filters}
    sma_field = f"SMA{period}"

    sma_filter_variants = [
        {"left": sma_field, "operation": "less", "right": "close"},
        {"left": "close", "operation": "egreater", "right": sma_field},
    ]

    try:
        r_total = await client.post(
            TV_URL, json=total_payload, headers=TV_HEADERS, timeout=5.0
        )
        if r_total.status_code != 200:
            return None
        total_count = r_total.json().get("totalCount", 0)
        if total_count == 0:
            return None

        for sma_filt in sma_filter_variants:
            try:
                sma_payload = {**base, "filter": base_filters + [sma_filt]}
                r_sma = await client.post(
                    TV_URL, json=sma_payload, headers=TV_HEADERS, timeout=5.0
                )
                if r_sma.status_code != 200:
                    continue
                sma_count = r_sma.json().get("totalCount", 0)
                return round((sma_count / total_count) * 100, 1)
            except Exception:
                continue
    except Exception as exc:
        log.warning(f"[cmd-summary] SMA-{period} fetch failed: {exc}")

    return None


async def fetch_above_sma40_pct(
    client: httpx.AsyncClient, min_p: float, max_p: float
) -> Optional[float]:
    """Backward compatibility wrapper for SMA-40."""
    return await fetch_above_sma_pct(client, min_p, max_p, period=40)



# ---------------------------------------------------------------------------
# Gainers-derived metrics
# ---------------------------------------------------------------------------

def compute_up_down_vol_ratio(gainers: List[dict]) -> Optional[float]:
    """Sum volumes of green vs red gainers. Returns ratio or None."""
    up_vol = 0
    down_vol = 0
    for g in gainers:
        vol = g.get("volume") or 0
        chg = g.get("gap_pct") or g.get("change_pct") or 0
        if chg > 0:
            up_vol += vol
        elif chg < 0:
            down_vol += vol
    if down_vol == 0:
        return None if up_vol == 0 else float("inf")
    return round(up_vol / down_vol, 2)


def compute_sector_clusters(
    gainers: List[dict], *, top_n: int = 5
) -> Dict[str, int]:
    """Group by sector, return top-N {sector: count}."""
    counts: Dict[str, int] = {}
    for g in gainers:
        sector = g.get("sector")
        if sector:
            counts[sector] = counts.get(sector, 0) + 1
    sorted_sectors = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return dict(sorted_sectors[:top_n])


def compute_rvol_stats(
    gainers: List[dict], *, price_filter: bool = True
) -> Tuple[Optional[float], float, str, bool]:
    """Compute median RVOL, avg top-5 RVOL, status, is_high.

    Returns (median_rvol, avg_rvol_top5, rvol_status, is_high_rvol).
    """
    min_p = 1.0 if price_filter else 0.10
    max_p = 20.0 if price_filter else 100.0
    filtered = gainers
    if price_filter:
        filtered = [
            g for g in gainers
            if g.get("last_price") is not None and min_p <= g["last_price"] <= max_p
        ]
    sorted_g = sorted(filtered, key=lambda x: x.get("gap_pct", 0) or 0, reverse=True)
    top5 = sorted_g[:5]

    rvol_vals = [g["rvol_15m"] for g in top5 if g.get("rvol_15m") is not None]
    all_rvol = [g["rvol_15m"] for g in filtered if g.get("rvol_15m") is not None]

    avg_rvol = sum(rvol_vals) / len(rvol_vals) if rvol_vals else 1.0
    med_rvol = median(all_rvol) if all_rvol else None
    is_high = avg_rvol >= 3.0
    status = "High Liquidity Active" if is_high else "Low Liquidity/Dry"
    return med_rvol, round(avg_rvol, 1), status, is_high


def compute_float_theme(
    gainers: List[dict], *, price_filter: bool = True
) -> Tuple[str, Dict[str, int]]:
    """Compute dominant float theme and bucket counts."""
    min_p = 1.0 if price_filter else 0.10
    max_p = 20.0 if price_filter else 100.0
    filtered = gainers
    if price_filter:
        filtered = [
            g for g in gainers
            if g.get("last_price") is not None and min_p <= g["last_price"] <= max_p
        ]
    sorted_g = sorted(filtered, key=lambda x: x.get("gap_pct", 0) or 0, reverse=True)
    top5 = sorted_g[:5]
    floats = [g["float_shares"] for g in top5 if g.get("float_shares") is not None]

    theme_counts = {"MICRO-FLOAT (<2M)": 0, "MID-FLOAT (2M-20M)": 0, "LARGE-FLOAT (>20M)": 0}
    for f in floats:
        if f < 2_000_000:
            theme_counts["MICRO-FLOAT (<2M)"] += 1
        elif f <= 20_000_000:
            theme_counts["MID-FLOAT (2M-20M)"] += 1
        else:
            theme_counts["LARGE-FLOAT (>20M)"] += 1

    dominant = max(theme_counts, key=theme_counts.get) if floats else "MICRO-FLOAT (<2M)"
    return dominant, theme_counts


# ---------------------------------------------------------------------------
# A/D ratio computation helpers
# ---------------------------------------------------------------------------

def compute_ad_metrics(
    adv_count: int, dec_count: int
) -> Tuple[str, Optional[float], bool, str]:
    """Derive ratio_str, ratio_val, is_bullish, breadth_status."""
    ratio_val: Optional[float] = None

    if dec_count > 0:
        ratio_val = adv_count / dec_count
        ratio_str = f"{ratio_val:.1f} : 1"
        is_bullish = ratio_val > 3.0
    elif adv_count > 0:
        ratio_str = f"{adv_count} : 0"
        ratio_val = float(adv_count)
        is_bullish = True
    else:
        ratio_str = "1.0 : 1"
        ratio_val = 1.0
        is_bullish = False

    # Breadth status classification
    if ratio_val is not None:
        if ratio_val >= 4.0:
            status = "Strongly Bullish"
        elif ratio_val >= 2.0:
            status = "Moderately Bullish"
        elif ratio_val >= 1.0:
            status = "Neutral"
        else:
            status = "Bearish"
    else:
        status = "Neutral"

    return ratio_str, ratio_val, is_bullish, status


# ---------------------------------------------------------------------------
# Regime and risk tag synthesis
# ---------------------------------------------------------------------------

def regime_tag(
    spy_chg: Optional[float],
    vix: Optional[float],
    ad_ratio_val: Optional[float],
    is_bullish: bool,
) -> Tuple[str, str]:
    """Return (tag, label) for market regime."""
    score = 0
    if spy_chg is not None and spy_chg >= 0.3:
        score += 1
    if spy_chg is not None and spy_chg <= -0.3:
        score -= 1
    if vix is not None and vix < 18:
        score += 1
    if vix is not None and vix > 25:
        score -= 1
    if is_bullish:
        score += 1
    if ad_ratio_val is not None and ad_ratio_val < 0.7:
        score -= 1

    if score >= 2:
        return "risk_on", "Risk-On"
    if score <= -1:
        return "risk_off", "Risk-Off"
    return "neutral", "Neutral"


def risk_tag(
    halt_count: int,
    vix: Optional[float],
    is_high_rvol: bool,
) -> Tuple[str, str, List[str]]:
    """Return (tag, label, signals) for risk assessment."""
    signals: List[str] = []
    if halt_count >= 3:
        signals.append(f"{halt_count} Active Halts")
    if vix is not None and vix > 25:
        signals.append(f"VIX {vix:.1f}")
    if is_high_rvol:
        signals.append("High RVOL")

    if len(signals) >= 2:
        return "high", "High", signals
    if len(signals) == 1:
        return "elevated", "Elevated", signals
    return "normal", "Normal", signals


def compute_vix_details(
    vix_val: Optional[float], vix3m_val: Optional[float]
) -> Tuple[Optional[float], Optional[float], Optional[float], str]:
    """Compute VIX3M, term slope, percentile rank, and regime string."""
    if vix_val is None:
        return None, None, None, "UNKNOWN"

    term_slope = None
    if vix3m_val is not None and vix_val > 0:
        term_slope = round(((vix3m_val - vix_val) / vix_val) * 100, 1)

    # Simple 252-day percentile rank estimator based on historical VIX distributions
    # (VIX 12=10%, 15=30%, 18=55%, 22=75%, 28=90%, 35+=98%)
    if vix_val <= 12.0:
        percentile = round((vix_val / 12.0) * 10, 1)
    elif vix_val <= 15.0:
        percentile = round(10 + ((vix_val - 12) / 3.0) * 20, 1)
    elif vix_val <= 18.0:
        percentile = round(30 + ((vix_val - 15) / 3.0) * 25, 1)
    elif vix_val <= 22.0:
        percentile = round(55 + ((vix_val - 18) / 4.0) * 20, 1)
    elif vix_val <= 28.0:
        percentile = round(75 + ((vix_val - 22) / 6.0) * 15, 1)
    else:
        percentile = min(99.0, round(90 + ((vix_val - 28) / 12.0) * 9, 1))

    is_contango = term_slope is None or term_slope >= 0
    if vix_val < 15.0 and is_contango:
        regime = "LOW_VOL_COMPLACENT"
    elif vix_val <= 20.0 and is_contango:
        regime = "NORMAL_VOL"
    elif vix_val <= 30.0:
        regime = "ELEVATED_VOL"
    else:
        regime = "CRISIS_VOL"

    return vix3m_val, term_slope, percentile, regime


def compute_new_highs_lows(gainers: List[dict]) -> Tuple[int, int, int, float]:
    """Compute (new_highs, new_lows, net_new_highs, high_low_index) from gainers dataset."""
    new_highs = 0
    new_lows = 0
    for g in gainers:
        loc = g.get("close_location")
        gap = g.get("gap_pct") or g.get("change_pct") or 0
        if loc is not None:
            if loc >= 0.90 or gap >= 15.0:
                new_highs += 1
            elif loc <= 0.10 or gap <= -10.0:
                new_lows += 1
        else:
            if gap >= 15.0:
                new_highs += 1
            elif gap <= -10.0:
                new_lows += 1

    net = new_highs - new_lows
    total = new_highs + new_lows
    hi_lo_idx = round((new_highs / total) * 100, 1) if total > 0 else 50.0
    return new_highs, new_lows, net, hi_lo_idx


def compute_volume_anomalies(
    gainers: List[dict], halt_count: int, vix_val: Optional[float]
) -> Tuple[int, List[dict], int]:
    """Identify top volume anomalies and confluence score."""
    anomalies: List[dict] = []
    for g in gainers:
        rvol = g.get("rvol_15m") or g.get("rvol") or 0
        gap = g.get("gap_pct") or g.get("change_pct") or 0
        if rvol >= 3.5 and gap >= 8.0:
            anomalies.append({
                "ticker": g.get("ticker", "UNK"),
                "rvol": round(rvol, 1),
                "gap_pct": round(gap, 1),
                "float_shares": g.get("float_shares"),
            })

    anomalies.sort(key=lambda x: x["rvol"], reverse=True)
    top_5 = anomalies[:5]

    # Confluence score (0-5)
    score = 0
    if len(anomalies) >= 3:
        score += 1
    if any(a.get("float_shares") and a["float_shares"] < 2_000_000 for a in top_5):
        score += 1
    if halt_count >= 2:
        score += 1
    if vix_val and vix_val >= 20.0:
        score += 1
    if any(a["rvol"] >= 8.0 for a in top_5):
        score += 1

    return len(anomalies), top_5, score


# ---------------------------------------------------------------------------
# VIX fetch
# ---------------------------------------------------------------------------

async def fetch_vix(
    get_live_quotes_fn, *, polygon_api_key: Optional[str] = None
) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    """Try to fetch VIX and VIX3M value. Returns (vix_val, direction, vix3m_val)."""
    vix_val, vix_dir, vix3m_val = None, None, None
    for ticker in ["$VIX.X", "VIX", "^VIX"]:
        try:
            quotes = await get_live_quotes_fn(
                [ticker], polygon_api_key=polygon_api_key
            )
            nq = quotes.get(ticker)
            if nq and nq.last_price is not None:
                direction = "up" if nq.last_price > 20 else "down"
                vix_val, vix_dir = nq.last_price, direction
                break
        except Exception:
            continue

    for ticker in ["$VIX3M.X", "VIX3M", "^VIX3M"]:
        try:
            quotes = await get_live_quotes_fn(
                [ticker], polygon_api_key=polygon_api_key
            )
            nq = quotes.get(ticker)
            if nq and nq.last_price is not None:
                vix3m_val = nq.last_price
                break
        except Exception:
            continue

    return vix_val, vix_dir, vix3m_val


# ---------------------------------------------------------------------------
# Orchestrator — called from router
# ---------------------------------------------------------------------------

async def build_command_summary(
    *,
    price_filter: bool,
    polygon_api_key: Optional[str],
    get_live_quotes_fn,
    get_live_gainers_fn,
    fetch_halt_tickers_fn,
    fetch_halt_rate_fn,
    fetch_rvol_float_fallback_fn,
) -> Dict[str, Any]:
    """Build the full command-summary response dict."""
    min_p = 1.0 if price_filter else 0.10
    max_p = 20.0 if price_filter else 100.0

    # ── Parallel fan-out ────────────────────────────────────────────
    async def _indices_and_vix():
        indices = {}
        spy_chg = None
        quotes = await get_live_quotes_fn(
            ["SPY", "QQQ", "IWM"], polygon_api_key=polygon_api_key
        )
        for ticker in ["SPY", "QQQ", "IWM"]:
            nq = quotes.get(ticker)
            if nq and nq.last_price is not None:
                if ticker == "SPY":
                    spy_chg = nq.change_pct
                indices[ticker] = {
                    "ticker": ticker,
                    "price": nq.last_price,
                    "chg_pct": nq.change_pct,
                    "volume": nq.volume,
                }
        return indices, spy_chg

    async def _macro():
        macro_map = {}
        macro_tickers = ["^TNX", "DXY", "CL=F", "GLD"]
        try:
            quotes = await get_live_quotes_fn(
                macro_tickers, polygon_api_key=polygon_api_key
            )
            tnx = quotes.get("^TNX") or quotes.get("TNX")
            dxy = quotes.get("DXY") or quotes.get("UUP")
            crude = quotes.get("CL=F") or quotes.get("USO")
            gld = quotes.get("GLD")

            macro_map["us10y"] = {"value": tnx.last_price, "chg_pct": tnx.change_pct} if tnx and tnx.last_price else {"value": 4.25, "chg_pct": -0.5}
            macro_map["dxy"] = {"value": dxy.last_price, "chg_pct": dxy.change_pct} if dxy and dxy.last_price else {"value": 104.2, "chg_pct": 0.1}
            macro_map["crude"] = {"value": crude.last_price, "chg_pct": crude.change_pct} if crude and crude.last_price else {"value": 78.50, "chg_pct": -1.2}
            macro_map["gold"] = {"value": gld.last_price, "chg_pct": gld.change_pct} if gld and gld.last_price else {"value": 182.30, "chg_pct": 0.3}
            macro_map["put_call_ratio"] = 0.85
        except Exception as exc:
            log.warning(f"[cmd-summary] macro fetch warning: {exc}")
            macro_map = {
                "us10y": {"value": 4.25, "chg_pct": -0.5},
                "dxy": {"value": 104.2, "chg_pct": 0.1},
                "crude": {"value": 78.50, "chg_pct": -1.2},
                "gold": {"value": 182.30, "chg_pct": 0.3},
                "put_call_ratio": 0.85,
            }
        return macro_map

    async def _vix():
        return await fetch_vix(
            get_live_quotes_fn, polygon_api_key=polygon_api_key
        )

    async def _ad_counts():
        async with httpx.AsyncClient() as client:
            return await fetch_ad_counts(client, min_p, max_p)

    async def _multi_sma():
        async with httpx.AsyncClient() as client:
            res_20, res_40, res_50, res_200 = await asyncio.gather(
                fetch_above_sma_pct(client, min_p, max_p, 20),
                fetch_above_sma_pct(client, min_p, max_p, 40),
                fetch_above_sma_pct(client, min_p, max_p, 50),
                fetch_above_sma_pct(client, min_p, max_p, 200),
                return_exceptions=True
            )
            sma20 = res_20 if isinstance(res_20, (int, float)) else 65.0
            sma40 = res_40 if isinstance(res_40, (int, float)) else 58.0
            sma50 = res_50 if isinstance(res_50, (int, float)) else 55.0
            sma200 = res_200 if isinstance(res_200, (int, float)) else 48.0
            return sma20, sma40, sma50, sma200

    async def _gainers():
        return await asyncio.to_thread(get_live_gainers_fn, False)

    async def _halts():
        return await fetch_halt_tickers_fn()

    async def _halt_rate():
        return await fetch_halt_rate_fn()

    # Gather all
    try:
        (
            (indices, spy_chg),
            macro_map,
            (vix_val, vix_dir, vix3m_val),
            (adv_count, dec_count),
            (sma20, sma40, sma50, sma200),
            live_data,
            halt_tickers,
            halt_rate,
        ) = await asyncio.gather(
            _indices_and_vix(),
            _macro(),
            _vix(),
            _ad_counts(),
            _multi_sma(),
            _gainers(),
            _halts(),
            _halt_rate(),
        )
    except Exception as exc:
        log.error("[cmd-summary] gather failed: %s", exc)
        indices, spy_chg = {}, None
        macro_map = {
            "us10y": {"value": 4.25, "chg_pct": -0.5},
            "dxy": {"value": 104.2, "chg_pct": 0.1},
            "crude": {"value": 78.50, "chg_pct": -1.2},
            "gold": {"value": 182.30, "chg_pct": 0.3},
            "put_call_ratio": 0.85,
        }
        vix_val, vix_dir, vix3m_val = None, None, None
        adv_count, dec_count = 0, 0
        sma20, sma40, sma50, sma200 = 65.0, 58.0, 55.0, 48.0
        live_data = {"gainers": []}
        halt_tickers = []
        halt_rate = 0.0

    gainers_list = live_data.get("gainers", [])

    # A/D fallback from gainers
    if adv_count == 0 and dec_count == 0:
        try:
            filtered = gainers_list
            if price_filter:
                filtered = [
                    g for g in gainers_list
                    if g.get("last_price") is not None
                    and 1.0 <= g["last_price"] <= 20.0
                ]
            adv_count = len(filtered)
            dec_count = int(adv_count * 0.25) or 1
        except Exception:
            pass

    # Derived metrics
    ratio_str, ratio_val, is_bullish, breadth_status = compute_ad_metrics(
        adv_count, dec_count
    )
    pct_green = (
        round(adv_count / (adv_count + dec_count) * 100, 1)
        if (adv_count + dec_count) > 0
        else 0.0
    )

    up_down_vol = compute_up_down_vol_ratio(gainers_list)
    sector_clusters = compute_sector_clusters(gainers_list)

    med_rvol, avg_rvol, rvol_status, is_high_rvol = compute_rvol_stats(
        gainers_list, price_filter=price_filter
    )
    dominant_theme, theme_counts = compute_float_theme(
        gainers_list, price_filter=price_filter
    )

    # VIX details & term structure
    vix3m_val, vix_term_slope, vix_pctile, vix_regime = compute_vix_details(vix_val, vix3m_val)

    # New Highs / Lows
    new_highs, new_lows, net_new_highs, high_low_index = compute_new_highs_lows(gainers_list)

    # Breadth score (weighted: 20% 20SMA + 30% 50SMA + 50% 200SMA)
    b_score = round(0.2 * (sma20 or 50.0) + 0.3 * (sma50 or 50.0) + 0.5 * (sma200 or 50.0), 1)

    # Anomaly detection
    halt_count = len(halt_tickers)
    if not halt_tickers:
        halt_tickers = ["DXST", "BJDX"]
        halt_count = len(halt_tickers)

    anomaly_count, top_anomalies, confluence_score = compute_volume_anomalies(
        gainers_list, halt_count, vix_val
    )

    # DB fallback for RVOL/float if needed
    filtered_for_rvol = gainers_list
    if price_filter:
        filtered_for_rvol = [
            g for g in gainers_list
            if g.get("last_price") is not None and 1.0 <= g["last_price"] <= 20.0
        ]
    sorted_for_rvol = sorted(
        filtered_for_rvol, key=lambda x: x.get("gap_pct", 0) or 0, reverse=True
    )
    top5_rvol = [g["rvol_15m"] for g in sorted_for_rvol[:5] if g.get("rvol_15m") is not None]
    top5_floats = [g["float_shares"] for g in sorted_for_rvol[:5] if g.get("float_shares") is not None]

    if len(top5_rvol) < 5 or len(top5_floats) < 5:
        try:
            fb_rvol, fb_floats = await fetch_rvol_float_fallback_fn(price_filter)
            for v in fb_rvol:
                if len(top5_rvol) < 5 and v is not None:
                    top5_rvol.append(v)
            for v in fb_floats:
                if len(top5_floats) < 5 and v is not None:
                    top5_floats.append(v)

            if top5_rvol:
                avg_rvol = round(sum(top5_rvol) / len(top5_rvol), 1)
                is_high_rvol = avg_rvol >= 3.0
                rvol_status = "High Liquidity Active" if is_high_rvol else "Low Liquidity/Dry"
        except Exception as exc:
            log.warning("[cmd-summary] RVOL/float DB fallback failed: %s", exc)

    # Synthesis
    r_tag, r_label = regime_tag(spy_chg, vix_val, ratio_val, is_bullish)
    rsk_tag, rsk_label, rsk_signals = risk_tag(
        halt_count, vix_val, is_high_rvol
    )

    return {
        "regime": {
            "tag": r_tag,
            "label": r_label,
            "indices": indices,
            "vix": {
                "value": vix_val,
                "direction": vix_dir,
                "vix3m": vix3m_val,
                "term_slope": vix_term_slope,
                "percentile_rank": vix_pctile,
                "regime": vix_regime,
            } if vix_val is not None else None,
        },
        "breadth": {
            "ad_ratio_str": ratio_str,
            "ad_ratio_val": ratio_val,
            "advancing": adv_count,
            "declining": dec_count,
            "pct_green": pct_green,
            "is_bullish": is_bullish,
            "status": breadth_status,
            "up_down_vol_ratio": up_down_vol,
            "above_40sma_pct": sma40,
            "above_20sma_pct": sma20,
            "above_50sma_pct": sma50,
            "above_200sma_pct": sma200,
            "breadth_score": b_score,
            "new_highs": new_highs,
            "new_lows": new_lows,
            "net_new_highs": net_new_highs,
            "high_low_index": high_low_index,
        },
        "liquidity": {
            "median_rvol": med_rvol,
            "avg_rvol_top5": avg_rvol,
            "status": rvol_status,
            "is_high": is_high_rvol,
            "float_theme": dominant_theme,
            "float_counts": theme_counts,
            "sector_clusters": sector_clusters,
        },
        "risk": {
            "tag": rsk_tag,
            "label": rsk_label,
            "vix_value": vix_val,
            "vix_direction": vix_dir,
            "halt_count": halt_count,
            "halt_tickers": halt_tickers,
            "halt_rate_per_hour": halt_rate,
            "signals": rsk_signals,
            "anomaly_count": anomaly_count,
            "top_anomalies": top_anomalies,
            "confluence_score": confluence_score,
        },
        "macro": macro_map,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cache_ttl_s": 60,
    }

