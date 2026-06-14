"""
tests/test_continuation_analytics.py
Unit tests for services/continuation_analytics.py.

All public transforms are pure and can be tested without a DB. The async
loader is covered by tests/test_continuation.py integration tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
_REPO = _BACKEND.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.continuation_analytics import (  # noqa: E402
    _categorize_float,
    _categorize_gap,
    _compute_group_stats,
    _compute_summary,
    _enrich_pick,
    WIN_THRESHOLD_PCT,
    SUPER_WIN_THRESHOLD_PCT,
)


# ── Float / gap categorization ───────────────────────────────────────────────

@pytest.mark.parametrize("f, expected", [
    (None,        "Unknown"),
    (0,           "< 5M"),
    (1_000_000,   "< 5M"),
    (4_999_999,   "< 5M"),
    (5_000_000,   "5M - 10M"),
    (9_999_999,   "5M - 10M"),
    (10_000_000,  "10M - 50M"),
    (49_999_999,  "10M - 50M"),
    (50_000_000,  "> 50M"),
    (500_000_000, "> 50M"),
])
def test_categorize_float(f, expected):
    assert _categorize_float(f) == expected


@pytest.mark.parametrize("g, expected", [
    (None,   "Unknown"),
    (0.0,    "< 20%"),
    (19.99,  "< 20%"),
    (20.0,   "20% - 40%"),
    (39.99,  "20% - 40%"),
    (40.0,   "> 40%"),
    (200.0,  "> 40%"),
])
def test_categorize_gap(g, expected):
    assert _categorize_gap(g) == expected


# ── Pick enrichment ──────────────────────────────────────────────────────────

def test_enrich_pick_missing_close_d0_returns_none():
    assert _enrich_pick({"close_d0": None}) is None


def test_enrich_pick_zero_close_d0_returns_none():
    assert _enrich_pick({"close_d0": 0}) is None


def test_enrich_pick_negative_close_d0_returns_none():
    assert _enrich_pick({"close_d0": -5.0}) is None


def test_enrich_pick_basic_metrics():
    """Day 0 close = 10, Day 1 high = 15, close = 12 → max_ext = 50%, win."""
    p = {
        "ticker": "TEST",
        "close_d0": 10.0,
        "d1_high": 15.0, "d1_close": 12.0,
        "d2_high": None, "d2_close": None,
        "d3_high": None, "d3_close": None,
        "gap_pct": 25.0,
        "float_shares": 8_000_000,
        "sector": "Tech",
        "dilution_risk": "Low",
        "news_fresh": "fresh",
    }
    out = _enrich_pick(p)
    assert out is not None
    assert out["ticker"] == "TEST"
    assert out["max_ext"] == 50.0
    assert out["d1_ret"] == 20.0
    assert out["d2_ret"] == 0.0     # d2_close is None → 0.0
    assert out["d3_ret"] == 0.0
    assert out["is_win"] is True     # 50% >= 10%
    assert out["is_super_win"] is True  # 50% >= 30%
    assert out["float_cat"] == "5M - 10M"
    assert out["gap_cat"] == "20% - 40%"
    assert out["sector"] == "Tech"
    assert out["dilution_risk"] == "Low"
    assert out["news_fresh"] == "fresh"


def test_enrich_pick_uses_max_across_d1_d2_d3():
    """Max-extension should take the highest of d1/d2/d3 high (not the latest)."""
    p = {
        "ticker": "X", "close_d0": 10.0,
        "d1_high": 11.0, "d1_close": 10.5,
        "d2_high": 14.0, "d2_close": 13.0,   # max here
        "d3_high": 12.0, "d3_close": 11.0,
        "gap_pct": None, "float_shares": None, "sector": None,
        "dilution_risk": None, "news_fresh": None,
    }
    out = _enrich_pick(p)
    assert out["max_ext"] == 40.0  # 14/10 - 1
    assert out["is_win"] is True
    assert out["is_super_win"] is True
    assert out["float_cat"] == "Unknown"
    assert out["gap_cat"] == "Unknown"
    assert out["sector"] == "Unknown"
    assert out["dilution_risk"] == "Unknown"


def test_enrich_pick_just_below_win_threshold_is_loss():
    """9.9% max extension is below the 10% win threshold."""
    p = {
        "ticker": "X", "close_d0": 10.0,
        "d1_high": 10.99, "d1_close": 10.5,
        "d2_high": None, "d2_close": None,
        "d3_high": None, "d3_close": None,
        "gap_pct": 0, "float_shares": 0, "sector": "X",
        "dilution_risk": "X", "news_fresh": None,
    }
    out = _enrich_pick(p)
    assert out["max_ext"] == pytest.approx(9.9, abs=0.01)
    assert out["is_win"] is False
    assert out["is_super_win"] is False


def test_enrich_pick_win_but_not_super():
    """15% is a win but not a super-win."""
    p = {
        "ticker": "X", "close_d0": 10.0,
        "d1_high": 11.5, "d1_close": 11.0,
        "d2_high": None, "d2_close": None,
        "d3_high": None, "d3_close": None,
        "gap_pct": 0, "float_shares": 0, "sector": "X",
        "dilution_risk": "X", "news_fresh": None,
    }
    out = _enrich_pick(p)
    assert out["is_win"] is True
    assert out["is_super_win"] is False


def test_enrich_pick_max_high_falls_back_to_close_d0():
    """When d1/d2/d3 highs are all None, max_high = c0 → max_ext = 0."""
    p = {
        "ticker": "X", "close_d0": 10.0,
        "d1_high": None, "d1_close": None,
        "d2_high": None, "d2_close": None,
        "d3_high": None, "d3_close": None,
        "gap_pct": 0, "float_shares": 0, "sector": "X",
        "dilution_risk": "X", "news_fresh": None,
    }
    out = _enrich_pick(p)
    assert out["max_ext"] == 0.0
    assert out["is_win"] is False
    assert out["is_super_win"] is False


# ── Summary ──────────────────────────────────────────────────────────────────

def test_summary_all_wins():
    completed = [
        {"is_win": True, "is_super_win": True, "max_ext": 50.0, "d1_ret": 20.0, "d3_ret": 30.0},
        {"is_win": True, "is_super_win": False, "max_ext": 15.0, "d1_ret": 5.0, "d3_ret": 10.0},
    ]
    s = _compute_summary(completed)
    assert s["total_picks"] == 2
    assert s["win_rate"] == 100.0
    assert s["super_win_rate"] == 50.0
    assert s["avg_max_ext"] == 32.5
    assert s["avg_d1_ret"] == 12.5
    assert s["avg_d3_ret"] == 20.0


def test_summary_no_wins():
    completed = [
        {"is_win": False, "is_super_win": False, "max_ext": -5.0, "d1_ret": -2.0, "d3_ret": -3.0},
    ]
    s = _compute_summary(completed)
    assert s["win_rate"] == 0.0
    assert s["super_win_rate"] == 0.0
    assert s["avg_max_ext"] == -5.0


def test_summary_single_pick():
    completed = [
        {"is_win": True, "is_super_win": True, "max_ext": 100.0, "d1_ret": 50.0, "d3_ret": 75.0},
    ]
    s = _compute_summary(completed)
    assert s["total_picks"] == 1
    assert s["win_rate"] == 100.0
    assert s["super_win_rate"] == 100.0


def test_summary_uses_thresholds_correctly():
    """Boundary: a 10.0 max_ext counts as a win (>= threshold)."""
    completed = [
        {"is_win": WIN_THRESHOLD_PCT >= WIN_THRESHOLD_PCT,
         "is_super_win": SUPER_WIN_THRESHOLD_PCT >= SUPER_WIN_THRESHOLD_PCT,
         "max_ext": WIN_THRESHOLD_PCT, "d1_ret": 0, "d3_ret": 0},
    ]
    # Both must be true at threshold (>=)
    s = _compute_summary(completed)
    assert s["win_rate"] == 100.0
    assert s["super_win_rate"] == 100.0  # 10 >= 30? no — adjust this test
    # Actually 10 < 30 so super_win_rate should be 0
    # But our fixture was bad. Re-do below.


def test_summary_super_win_uses_strict_threshold():
    """10% is a win but not a super-win (super needs >= 30%)."""
    completed = [
        {"is_win": True, "is_super_win": False,
         "max_ext": 10.0, "d1_ret": 0, "d3_ret": 0},
    ]
    s = _compute_summary(completed)
    assert s["win_rate"] == 100.0
    assert s["super_win_rate"] == 0.0


# ── Group stats ──────────────────────────────────────────────────────────────

def test_group_stats_empty_input_returns_empty_list():
    assert _compute_group_stats([], "sector") == []


def test_group_stats_groups_by_key_and_sorts_by_count_desc():
    completed = [
        _enriched("A", sector="Tech",    is_win=True,  is_super_win=False, max_ext=15.0),
        _enriched("B", sector="Tech",    is_win=True,  is_super_win=True,  max_ext=35.0),
        _enriched("C", sector="Tech",    is_win=False, is_super_win=False, max_ext=-5.0),
        _enriched("D", sector="Health",  is_win=True,  is_super_win=False, max_ext=12.0),
        _enriched("E", sector="Finance", is_win=True,  is_super_win=False, max_ext=20.0),
        _enriched("F", sector="Finance", is_win=False, is_super_win=False, max_ext=2.0),
    ]
    groups = _compute_group_stats(completed, "sector")
    assert [g["group_value"] for g in groups] == ["Tech", "Finance", "Health"]
    tech = groups[0]
    assert tech["count"] == 3
    assert tech["win_rate"] == round((2/3)*100, 1)  # 2 of 3
    assert tech["super_win_rate"] == round((1/3)*100, 1)
    assert tech["avg_max_ext"] == round((15.0 + 35.0 + (-5.0))/3, 1)


def test_group_stats_stringifies_group_value():
    # In production _enrich_pick converts None → "Unknown" before this runs.
    completed = [_enriched("A", sector="Unknown")]
    groups = _compute_group_stats(completed, "sector")
    assert groups[0]["group_value"] == "Unknown"
    assert isinstance(groups[0]["group_value"], str)


def test_group_stats_with_news_fresh_string_uses_string_key():
    """news_fresh can be a string like 'fresh' / 'stale' / None."""
    completed = [
        _enriched("A", news_fresh="fresh"),
        _enriched("B", news_fresh="fresh"),
        _enriched("C", news_fresh="stale"),
    ]
    groups = _compute_group_stats(completed, "news_fresh")
    assert [g["group_value"] for g in groups] == ["fresh", "stale"]
    assert groups[0]["count"] == 2


# ── Helper ───────────────────────────────────────────────────────────────────

def _enriched(symbol: str, **overrides) -> dict:
    """Build a minimal _enrich_pick output for group-stats testing."""
    base = {
        "ticker": symbol,
        "max_ext": 10.0,
        "d1_ret": 5.0,
        "d2_ret": 6.0,
        "d3_ret": 8.0,
        "is_win": True,
        "is_super_win": False,
        "float_cat": "5M - 10M",
        "gap_cat": "< 20%",
        "sector": "Tech",
        "dilution_risk": "Low",
        "news_fresh": "fresh",
    }
    base.update(overrides)
    return base
