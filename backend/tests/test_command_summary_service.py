"""
tests/test_command_summary_service.py
Unit tests for the pure synthesis functions in command_summary_service.
"""
import pytest

from services.command_summary_service import (
    compute_ad_metrics,
    compute_sector_clusters,
    compute_up_down_vol_ratio,
    regime_tag,
    risk_tag,
)


# ── regime_tag ──────────────────────────────────────────────────────────────

class TestRegimeTag:
    def test_risk_on(self):
        tag, label = regime_tag(spy_chg=1.0, vix=15.0, ad_ratio_val=4.0, is_bullish=True)
        assert tag == "risk_on"
        assert label == "Risk-On"

    def test_risk_off(self):
        tag, label = regime_tag(spy_chg=-0.5, vix=28.0, ad_ratio_val=0.5, is_bullish=False)
        assert tag == "risk_off"

    def test_neutral(self):
        tag, label = regime_tag(spy_chg=0.1, vix=19.0, ad_ratio_val=1.2, is_bullish=False)
        assert tag == "neutral"

    def test_none_inputs(self):
        tag, label = regime_tag(spy_chg=None, vix=None, ad_ratio_val=None, is_bullish=False)
        assert tag == "neutral"


# ── risk_tag ────────────────────────────────────────────────────────────────

class TestRiskTag:
    def test_normal(self):
        tag, label, signals = risk_tag(halt_count=1, vix=18.0, is_high_rvol=False)
        assert tag == "normal"
        assert signals == []

    def test_elevated(self):
        tag, label, signals = risk_tag(halt_count=3, vix=18.0, is_high_rvol=False)
        assert tag == "elevated"
        assert len(signals) == 1

    def test_high(self):
        tag, label, signals = risk_tag(halt_count=5, vix=30.0, is_high_rvol=True)
        assert tag == "high"
        assert len(signals) >= 2


# ── compute_ad_metrics ──────────────────────────────────────────────────────

class TestComputeAdMetrics:
    def test_bullish(self):
        ratio_str, ratio_val, is_bullish, status = compute_ad_metrics(400, 80)
        assert is_bullish is True
        assert ratio_val == pytest.approx(5.0)
        assert status == "Strongly Bullish"

    def test_bearish(self):
        _, ratio_val, is_bullish, status = compute_ad_metrics(50, 200)
        assert is_bullish is False
        assert status == "Bearish"

    def test_no_decliners(self):
        ratio_str, _, is_bullish, _ = compute_ad_metrics(100, 0)
        assert is_bullish is True
        assert "100" in ratio_str

    def test_zero_both(self):
        _, _, is_bullish, _ = compute_ad_metrics(0, 0)
        assert is_bullish is False


# ── compute_up_down_vol_ratio ───────────────────────────────────────────────

class TestUpDownVolRatio:
    def test_basic(self):
        gainers = [
            {"gap_pct": 5.0, "volume": 100_000},
            {"gap_pct": -3.0, "volume": 50_000},
        ]
        ratio = compute_up_down_vol_ratio(gainers)
        assert ratio == 2.0

    def test_no_volume(self):
        ratio = compute_up_down_vol_ratio([])
        assert ratio is None


# ── compute_sector_clusters ─────────────────────────────────────────────────

class TestSectorClusters:
    def test_top5(self):
        gainers = [
            {"sector": "Healthcare"},
            {"sector": "Healthcare"},
            {"sector": "Energy"},
            {"sector": "Technology"},
            {"sector": "Technology"},
            {"sector": "Technology"},
            {"sector": None},
        ]
        result = compute_sector_clusters(gainers, top_n=2)
        assert "Technology" in result
        assert len(result) <= 2

    def test_empty(self):
        result = compute_sector_clusters([])
        assert result == {}
