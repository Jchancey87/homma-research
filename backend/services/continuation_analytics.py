"""
services/continuation_analytics.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deep module that owns the continuation-picks performance scorecard.

Public surface:

    async def compute_performance_stats(db) -> dict

Router forwards to this. All pure transforms are split into helpers that
can be unit-tested without a DB.

Originally extracted from routers/continuation.py:144-282 (RFC-001).
"""
from __future__ import annotations

import logging
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)

# Win / super-win thresholds (percent above Day-0 close)
WIN_THRESHOLD_PCT = 10.0
SUPER_WIN_THRESHOLD_PCT = 30.0

# Float tier boundaries (shares)
_FLOAT_TIERS = (
    (5_000_000,        "< 5M"),
    (10_000_000,       "5M - 10M"),
    (50_000_000,       "10M - 50M"),
)
_GAP_TIERS = (
    (20.0, "< 20%"),
    (40.0, "20% - 40%"),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def compute_performance_stats(db: asyncpg.Connection) -> dict:
    """
    Compute a statistical scorecard of continuation picks performance.

    Returns:
        {"summary": {...}, "groups": {float_category, gap_category, sector,
                                       dilution_risk, news_freshness}}
    """
    rows = await db.fetch(
        """SELECT ticker, date, gap_pct, float_shares, sector, rank, close_d0,
                  d1_open, d1_high, d1_low, d1_close, d1_volume,
                  d2_open, d2_high, d2_low, d2_close, d2_volume,
                  d3_open, d3_high, d3_low, d3_close, d3_volume,
                  market_cap, shares_outstanding, cash, runway_months, dilution_risk, news_fresh
           FROM continuation_picks
           WHERE close_d0 IS NOT NULL"""
    )
    picks = rows_to_dicts(rows)
    if not picks:
        return {"summary": {}, "groups": {}}

    completed = [p for p in (_enrich_pick(p) for p in picks) if p is not None]
    if not completed:
        return {"summary": {}, "groups": {}}

    return {
        "summary": _compute_summary(completed),
        "groups": {
            "float_category":  _compute_group_stats(completed, "float_cat"),
            "gap_category":    _compute_group_stats(completed, "gap_cat"),
            "sector":          _compute_group_stats(completed, "sector"),
            "dilution_risk":   _compute_group_stats(completed, "dilution_risk"),
            "news_freshness":  _compute_group_stats(completed, "news_fresh"),
        },
    }


# ─── asyncpg Record → plain dict shim ────────────────────────────────────────

def rows_to_dicts(rows) -> list[dict]:
    """Convert asyncpg Record list to a list of plain dicts."""
    return [dict(r) for r in rows]


# ─── Pick enrichment (pure) ──────────────────────────────────────────────────

def _enrich_pick(p: dict) -> Optional[dict]:
    """
    Compute max-extension, day-returns, win flags, and category labels for a
    single continuation pick. Returns None for picks missing a valid close_d0.
    """
    c0 = p.get("close_d0")
    if not c0 or c0 <= 0:
        return None

    d1_h, d2_h, d3_h = p.get("d1_high"), p.get("d2_high"), p.get("d3_high")
    d1_c, d2_c, d3_c = p.get("d1_close"), p.get("d2_close"), p.get("d3_close")

    highs = [h for h in (d1_h, d2_h, d3_h) if h is not None]
    max_high = max(highs) if highs else c0
    max_ext = ((max_high - c0) / c0) * 100.0

    d1_ret = ((d1_c - c0) / c0) * 100.0 if d1_c else 0.0
    d2_ret = ((d2_c - c0) / c0) * 100.0 if d2_c else 0.0
    d3_ret = ((d3_c - c0) / c0) * 100.0 if d3_c else 0.0

    return {
        "ticker":         p["ticker"],
        "max_ext":        max_ext,
        "d1_ret":         d1_ret,
        "d2_ret":         d2_ret,
        "d3_ret":         d3_ret,
        "is_win":         max_ext >= WIN_THRESHOLD_PCT,
        "is_super_win":   max_ext >= SUPER_WIN_THRESHOLD_PCT,
        "float_cat":      _categorize_float(p.get("float_shares")),
        "gap_cat":        _categorize_gap(p.get("gap_pct")),
        "sector":         p.get("sector") or "Unknown",
        "dilution_risk":  p.get("dilution_risk") or "Unknown",
        "news_fresh":     p.get("news_fresh"),
    }


def _categorize_float(f) -> str:
    if f is None:
        return "Unknown"
    for boundary, label in _FLOAT_TIERS:
        if f < boundary:
            return label
    return "> 50M"


def _categorize_gap(g) -> str:
    if g is None:
        return "Unknown"
    for boundary, label in _GAP_TIERS:
        if g < boundary:
            return label
    return "> 40%"


# ─── Summary (pure) ──────────────────────────────────────────────────────────

def _compute_summary(completed: list[dict]) -> dict:
    total = len(completed)
    wins = sum(1 for p in completed if p["is_win"])
    super_wins = sum(1 for p in completed if p["is_super_win"])
    avg_max_ext = sum(p["max_ext"] for p in completed) / total
    avg_d1_ret = sum(p["d1_ret"] for p in completed) / total
    avg_d3_ret = sum(p["d3_ret"] for p in completed) / total

    return {
        "total_picks":     total,
        "win_rate":        round((wins / total) * 100.0, 1),
        "super_win_rate":  round((super_wins / total) * 100.0, 1),
        "avg_max_ext":     round(avg_max_ext, 1),
        "avg_d1_ret":      round(avg_d1_ret, 1),
        "avg_d3_ret":      round(avg_d3_ret, 1),
    }


# ─── Group stats (pure) ──────────────────────────────────────────────────────

def _compute_group_stats(completed: list[dict], group_key: str) -> list[dict]:
    """Group by `group_key` and compute win-rate, super-win-rate, avg max-ext."""
    grouped: dict = {}
    for p in completed:
        val = p[group_key]
        grouped.setdefault(val, []).append(p)

    stats: list[dict] = []
    for name, items in grouped.items():
        g_total = len(items)
        g_wins = sum(1 for x in items if x["is_win"])
        g_super = sum(1 for x in items if x["is_super_win"])
        g_avg_ext = sum(x["max_ext"] for x in items) / g_total
        stats.append({
            "group_value":     str(name),
            "count":           g_total,
            "win_rate":        round((g_wins / g_total) * 100.0, 1),
            "super_win_rate":  round((g_super / g_total) * 100.0, 1),
            "avg_max_ext":     round(g_avg_ext, 1),
        })
    stats.sort(key=lambda x: x["count"], reverse=True)
    return stats
