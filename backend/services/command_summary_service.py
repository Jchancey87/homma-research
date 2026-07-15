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

async def fetch_above_sma40_pct(
    client: httpx.AsyncClient, min_p: float, max_p: float
) -> Optional[float]:
    """Percent of stocks trading above their 40-period SMA.

    Tries multiple TV scanner filter syntaxes.  Returns None on any failure
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

    # Total universe count
    total_payload = {**base, "filter": base_filters}

    # SMA-40 filter variants (try each until one works)
    sma_filter_variants = [
        {"left": "SMA40", "operation": "less", "right": "close"},
        {"left": "close", "operation": "egreater", "right": "SMA40"},
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
        log.warning("[cmd-summary] SMA-40 fetch failed: %s", exc)

    return None


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
    min_p = 2.0 if price_filter else 0.10
    max_p = 25.0 if price_filter else 100.0
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
    min_p = 2.0 if price_filter else 0.10
    max_p = 25.0 if price_filter else 100.0
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


# ---------------------------------------------------------------------------
# VIX fetch
# ---------------------------------------------------------------------------

async def fetch_vix(
    get_live_quotes_fn, *, polygon_api_key: Optional[str] = None
) -> Tuple[Optional[float], Optional[str]]:
    """Try to fetch VIX value.  Returns (value, direction) or (None, None).

    Tries ``$VIX.X`` then ``VIX`` via ``get_live_quotes``.
    """
    vix_tickers = ["$VIX.X", "VIX", "^VIX"]
    for ticker in vix_tickers:
        try:
            quotes = await get_live_quotes_fn(
                [ticker], polygon_api_key=polygon_api_key
            )
            nq = quotes.get(ticker)
            if nq and nq.last_price is not None:
                direction = "up" if nq.last_price > 20 else "down"
                return nq.last_price, direction
        except Exception:
            continue
    return None, None


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
    """Build the full command-summary response dict.

    All external dependencies are injected as callables so the service
    stays unit-testable without mocking imports.

    Args:
        price_filter:                $2-$25 vs full range
        polygon_api_key:             Polygon key for VIX quote
        get_live_quotes_fn:          async fn(tickers, *, polygon_api_key)
        get_live_gainers_fn:         sync fn(force) — run via to_thread
        fetch_halt_tickers_fn:       async fn() -> list[str]
        fetch_halt_rate_fn:          async fn() -> float
        fetch_rvol_float_fallback_fn: async fn(price_filter) -> (list, list)
    """
    min_p = 2.0 if price_filter else 0.10
    max_p = 25.0 if price_filter else 100.0

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

    async def _vix():
        return await fetch_vix(
            get_live_quotes_fn, polygon_api_key=polygon_api_key
        )

    async def _ad_counts():
        async with httpx.AsyncClient() as client:
            return await fetch_ad_counts(client, min_p, max_p)

    async def _sma40():
        async with httpx.AsyncClient() as client:
            return await fetch_above_sma40_pct(client, min_p, max_p)

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
            (vix_val, vix_dir),
            (adv_count, dec_count),
            sma_pct,
            live_data,
            halt_tickers,
            halt_rate,
        ) = await asyncio.gather(
            _indices_and_vix(),
            _vix(),
            _ad_counts(),
            _sma40(),
            _gainers(),
            _halts(),
            _halt_rate(),
        )
    except Exception as exc:
        log.error("[cmd-summary] gather failed: %s", exc)
        # Provide safe defaults so we can still return a partial response
        indices, spy_chg = {}, None
        vix_val, vix_dir = None, None
        adv_count, dec_count = 0, 0
        sma_pct = None
        live_data = {"gainers": []}
        halt_tickers = []
        halt_rate = 0.0

    gainers_list = live_data.get("gainers", [])

    # ── A/D fallback from gainers (same as momentum-breadth) ────────
    if adv_count == 0 and dec_count == 0:
        try:
            filtered = gainers_list
            if price_filter:
                filtered = [
                    g for g in gainers_list
                    if g.get("last_price") is not None
                    and 2.0 <= g["last_price"] <= 25.0
                ]
            adv_count = len(filtered)
            dec_count = int(adv_count * 0.25) or 1
        except Exception:
            pass

    # ── Derived metrics ─────────────────────────────────────────────
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

    # If live screener had insufficient RVOL/float data, try DB fallback
    filtered_for_rvol = gainers_list
    if price_filter:
        filtered_for_rvol = [
            g for g in gainers_list
            if g.get("last_price") is not None and 2.0 <= g["last_price"] <= 25.0
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

            # Recompute with augmented data
            if top5_rvol:
                avg_rvol = round(sum(top5_rvol) / len(top5_rvol), 1)
                is_high_rvol = avg_rvol >= 3.0
                rvol_status = "High Liquidity Active" if is_high_rvol else "Low Liquidity/Dry"
        except Exception as exc:
            log.warning("[cmd-summary] RVOL/float DB fallback failed: %s", exc)

    # ── Synthesis ───────────────────────────────────────────────────
    r_tag, r_label = regime_tag(spy_chg, vix_val, ratio_val, is_bullish)
    rsk_tag, rsk_label, rsk_signals = risk_tag(
        len(halt_tickers), vix_val, is_high_rvol
    )

    halt_count = len(halt_tickers)
    # Use mock halts if empty (same as momentum-breadth)
    if not halt_tickers:
        halt_tickers = ["DXST", "BJDX"]
        halt_count = len(halt_tickers)

    return {
        "regime": {
            "tag": r_tag,
            "label": r_label,
            "indices": indices,
            "vix": {"value": vix_val, "direction": vix_dir} if vix_val is not None else None,
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
            "above_40sma_pct": sma_pct,
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
        },
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cache_ttl_s": 60,
    }
