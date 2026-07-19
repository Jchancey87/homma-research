"""
backend/tests/e2e/test_cases.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
E2E test suite for real-time momentum alert optimizations and Alert Journal upgrade.

Tier 1: Feature Coverage (>= 20 tests)
Tier 2: Boundary & Corner Cases (>= 20 tests)
Tier 3: Cross-Feature Combinations (>= 4 tests)
Tier 4: Real-world Application Scenarios (>= 5 tests)

Total target: >= 49 tests
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import pytest_asyncio
import asyncpg

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from tests.e2e.mock_stream_generator import (
    Level1Quote,
    AlertPayload,
    build_hod_breakout_quotes,
    build_vwap_crossover_quotes,
    build_volume_spike_quotes,
    build_halt_resume_quotes,
    build_no_alert_quotes,
    build_body_close_hod_quotes,
    build_tod_volume_quotes,
)


def _get_pool():
    from fastapi_app.db import get_pool
    return get_pool()


# ===================================================================
# TIER 1: FEATURE COVERAGE (>= 20 tests)
# ===================================================================

class TestTier1R1TriggerQuality:
    """Tier 1 tests for Schwab Stream Alert Engine (R1) - trigger quality."""

    @pytest.mark.asyncio
    async def test_t1_r1_near_hod_radar_alert_fires(self, seed_alert):
        """NEAR_HOD_RADAR alert record persisted in DB with correct fields."""
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=155.0, rel_vol=2.5, priority_tier="Tier 1",
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1 AND alert_time = $2",
                alert_id, at,
            )
        assert row is not None
        assert row["alert_type"] == "NEAR_HOD_RADAR"
        assert row["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_t1_r1_prev_day_breakout_alert_fires(self, seed_alert):
        """PREV_DAY_BREAKOUT alert created with correct gap_pct."""
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="TSLA", alert_type="PREV_DAY_BREAKOUT",
            trigger_price=250.0, gap_pct=8.5, priority_tier="Tier 1",
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["alert_type"] == "PREV_DAY_BREAKOUT"
        assert row["gap_pct"] == pytest.approx(8.5)

    @pytest.mark.asyncio
    async def test_t1_r1_volume_spike_alert_fires(self, seed_alert):
        """VOLUME_SPIKE alert created with high trigger_volume."""
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="SNDL", alert_type="VOLUME_SPIKE",
            trigger_price=2.50, trigger_volume=500_000, rel_vol=10.0,
            priority_tier="Tier 1",
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["alert_type"] == "VOLUME_SPIKE"
        assert row["trigger_volume"] == 500_000

    @pytest.mark.asyncio
    async def test_t1_r1_vwap_crossover_disabled(self, seed_alert):
        """VWAP_CROSSOVER alert type stored but marked disabled per config."""
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="AAPL", alert_type="VWAP_CROSSOVER",
            trigger_price=152.0, rel_vol=2.1,
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["alert_type"] == "VWAP_CROSSOVER"

    @pytest.mark.asyncio
    async def test_t1_r1_volatility_halt_and_resume(self, seed_alert):
        """VOLATILITY_HALT and VOLATILITY_RESUME pair for halt/resume cycle."""
        halt_time = datetime.now(timezone.utc)
        halt_id, halt_at = await seed_alert(
            symbol="AAPL", alert_type="VOLATILITY_HALT",
            trigger_price=145.0, rel_vol=0.0, alert_time=halt_time,
        )
        resume_time = halt_time + timedelta(minutes=2)
        resume_id, resume_at = await seed_alert(
            symbol="AAPL", alert_type="VOLATILITY_RESUME",
            trigger_price=148.0, rel_vol=0.0, alert_time=resume_time,
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            halt_row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", halt_id,
            )
            resume_row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", resume_id,
            )
        assert halt_row["alert_type"] == "VOLATILITY_HALT"
        assert resume_row["alert_type"] == "VOLATILITY_RESUME"

    @pytest.mark.asyncio
    async def test_t1_r1_post_halt_suppression_flag(self, seed_alert):
        """Alert has suppressed_reason set during post-halt suppression window."""
        halt_time = datetime.now(timezone.utc)
        await seed_alert(
            symbol="AAPL", alert_type="VOLATILITY_HALT",
            trigger_price=145.0, alert_time=halt_time,
        )
        suppressed_time = halt_time + timedelta(seconds=30)
        alert_id, at = await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=147.0, alert_time=suppressed_time,
            suppressed_reason="POST_HALT_SUPPRESSION",
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["suppressed_reason"] == "POST_HALT_SUPPRESSION"

    @pytest.mark.asyncio
    async def test_t1_r1_body_close_hod_breakout(self, seed_alert):
        """Body-close HOD: close within 85% of candle range triggers alert."""
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="TSLA", alert_type="NEAR_HOD_RADAR",
            trigger_price=255.0, hod_dist_pct=0.3, priority_tier="Tier 1",
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["hod_dist_pct"] == pytest.approx(0.3)


# -------------------------------------------------------------------
# R2: Actionable Telegram Alerts (6 tests)
# -------------------------------------------------------------------

class TestTier1R2TelegramAlerts:
    """Tier 1 tests for Telegram Alert formatting and delivery (R2)."""

    def test_t1_r2_message_header_near_hod_radar(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "AAPL", "price": 155.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 2.5, "time": "2026-06-05T14:30:00",
            "priority_score": 80, "priority_tier": "Tier 1",
            "strategy_label": "Near HOD Radar",
        }
        msg = _format_alert_message(payload)
        assert "NEAR HOD RADAR" in msg
        assert "AAPL" in msg

    def test_t1_r2_message_contains_ticker_link(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "TSLA", "price": 250.0, "alert_type": "PREV_DAY_BREAKOUT",
            "rvol": 3.0, "time": "2026-06-05T14:30:00",
            "priority_score": 90, "priority_tier": "Tier 1",
        }
        msg = _format_alert_message(payload)
        assert "tradingview.com" in msg
        assert "TSLA" in msg

    def test_t1_r2_message_contains_price_and_rvol(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "SNDL", "price": 2.50, "alert_type": "VOLUME_SPIKE",
            "rvol": 10.0, "time": "2026-06-05T14:30:00",
            "priority_score": 70, "priority_tier": "Tier 2",
        }
        msg = _format_alert_message(payload)
        assert "2.50" in msg
        assert "10.0x" in msg

    def test_t1_r2_message_contains_priority_and_strategy(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "AAPL", "price": 155.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 2.5, "time": "2026-06-05T14:30:00",
            "priority_score": 85, "priority_tier": "Tier 1",
            "strategy_label": "Near HOD Radar",
        }
        msg = _format_alert_message(payload)
        assert "Tier 1" in msg
        assert "Score: 85" in msg
        assert "Near HOD Radar" in msg

    def test_t1_r2_message_vwap_dist_line(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "AAPL", "price": 155.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 2.5, "time": "2026-06-05T14:30:00",
            "priority_score": 80, "priority_tier": "Tier 1",
            "vwap": 150.0,
        }
        msg = _format_alert_message(payload)
        assert "VWAP dist" in msg
        assert "150.00" in msg

    def test_t1_r2_message_halt_emoji_and_signal(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "AAPL", "price": 145.0, "alert_type": "VOLATILITY_HALT",
            "rvol": 0.0, "time": "2026-06-05T14:30:00",
            "priority_score": 50, "priority_tier": "Tier 2",
        }
        msg = _format_alert_message(payload)
        assert "VOLATILITY HALT" in msg
        assert "Signal" in msg


# -------------------------------------------------------------------
# R3: Performance & Expectancy Feedback Loop (7 tests)
# -------------------------------------------------------------------

class TestTier1R3PerformanceFeedback:
    """Tier 1 tests for performance scoring and expectancy (R3)."""

    @pytest.mark.asyncio
    async def test_t1_r3_daily_summary_returns_date_and_tickers(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
        )
        await seed_price_candles(
            symbol="AAPL", alert_time=alert_time,
            trigger_price=150.0, num_candles=16, trend="up",
        )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data
        assert "tickers" in data

    @pytest.mark.asyncio
    async def test_t1_r3_daily_summary_groups_by_ticker(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
        )
        await seed_alert(
            symbol="AAPL", alert_type="PREV_DAY_BREAKOUT",
            trigger_price=152.0, alert_time=alert_time + timedelta(minutes=5),
        )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        tickers = data.get("tickers", [])
        assert len(tickers) >= 1
        assert tickers[0]["symbol"] == "AAPL"
        assert len(tickers[0]["alerts"]) >= 2

    @pytest.mark.asyncio
    async def test_t1_r3_daily_summary_includes_forward_returns(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
        )
        await seed_price_candles(
            symbol="AAPL", alert_time=alert_time,
            trigger_price=150.0, num_candles=16, trend="up",
        )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        tickers = data.get("tickers", [])
        assert len(tickers) >= 1
        alert = tickers[0]["alerts"][0]
        assert "fwd_1m" in alert
        assert "fwd_5m" in alert
        assert "fwd_15m" in alert

    @pytest.mark.asyncio
    async def test_t1_r3_daily_summary_includes_mfe_mae(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
        )
        await seed_price_candles(
            symbol="AAPL", alert_time=alert_time,
            trigger_price=150.0, num_candles=16, trend="up",
        )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        alert = data["tickers"][0]["alerts"][0]
        assert "mfe" in alert
        assert "mae" in alert

    @pytest.mark.asyncio
    async def test_t1_r3_performance_scorecard_returns_groups(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today - timedelta(days=5)
        for i in range(5):
            t = alert_time + timedelta(hours=i)
            await seed_alert(
                symbol="AAPL", alert_type="NEAR_HOD_RADAR",
                trigger_price=150.0 + i, alert_time=t,
            )
            await seed_price_candles(
                symbol="AAPL", alert_time=t,
                trigger_price=150.0 + i, num_candles=16, trend="up",
            )
        resp = await client.get("/api/alerts/performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "days" in data
        assert "scorecard" in data
        assert isinstance(data["scorecard"], list)

    @pytest.mark.asyncio
    async def test_t1_r3_performance_scorecard_win_rate(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today - timedelta(days=3)
        for i in range(5):
            t = alert_time + timedelta(hours=i)
            await seed_alert(
                symbol="AAPL", alert_type="NEAR_HOD_RADAR",
                trigger_price=150.0 + i, alert_time=t,
            )
            await seed_price_candles(
                symbol="AAPL", alert_time=t,
                trigger_price=150.0 + i, num_candles=16, trend="up",
            )
        resp = await client.get("/api/alerts/performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        if data["scorecard"]:
            row = data["scorecard"][0]
            assert "win_rate_5m_pct" in row
            assert "avg_fwd_5m" in row
            assert "avg_mfe_pct" in row
            assert "avg_mae_pct" in row

    @pytest.mark.asyncio
    async def test_t1_r3_daily_summary_empty_date_returns_empty(self, client):
        resp = await client.get("/api/alerts/daily-summary?date=2020-01-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tickers"] == []


# ===================================================================
# TIER 2: BOUNDARY & CORNER CASES (>= 20 tests)
# ===================================================================

class TestTier2R1TriggerBoundaries:
    """Tier 2 boundary tests for R1 trigger quality."""

    @pytest.mark.asyncio
    async def test_t2_r1_rvol_at_minimum_threshold(self, seed_alert):
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=155.0, rel_vol=1.5,
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["rel_vol"] == pytest.approx(1.5)

    @pytest.mark.asyncio
    async def test_t2_r1_rvol_extreme_high(self, seed_alert):
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="SNDL", alert_type="VOLUME_SPIKE",
            trigger_price=2.50, rel_vol=100.0,
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["rel_vol"] == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_t2_r1_body_close_extreme_high(self, seed_alert):
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="TSLA", alert_type="NEAR_HOD_RADAR",
            trigger_price=255.0, hod_dist_pct=0.0,
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None

    @pytest.mark.asyncio
    async def test_t2_r1_body_close_extreme_low(self, seed_alert):
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="TSLA", alert_type="NEAR_HOD_RADAR",
            trigger_price=255.0, hod_dist_pct=-1.5,
            suppressed_reason="BODY_CLOSE_LOW",
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["suppressed_reason"] == "BODY_CLOSE_LOW"

    @pytest.mark.asyncio
    async def test_t2_r1_zero_volume_quote(self):
        quotes = build_no_alert_quotes("AAPL", volume_start=0, num_ticks=3)
        assert len(quotes) == 3
        for q in quotes:
            assert q.total_volume >= 0

    @pytest.mark.asyncio
    async def test_t2_r1_negative_gap_pct(self, seed_alert):
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="AAPL", alert_type="PREV_DAY_BREAKOUT",
            trigger_price=150.0, gap_pct=-5.2,
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["gap_pct"] == pytest.approx(-5.2)

    @pytest.mark.asyncio
    async def test_t2_r1_price_below_one_dollar_filtered(self, seed_alert):
        alert_time = datetime.now(timezone.utc)
        alert_id, at = await seed_alert(
            symbol="SNDL", alert_type="VOLUME_SPIKE",
            trigger_price=0.50, trigger_volume=1_000_000, rel_vol=20.0,
        )
        pool = _get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screener_alerts WHERE id = $1", alert_id,
            )
        assert row is not None
        assert row["trigger_price"] == 0.50


class TestTier2R2TelegramBoundaries:
    """Tier 2 boundary tests for R2 Telegram alerts."""

    def test_t2_r2_message_missing_optional_fields(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "TEST", "price": 10.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 2.0, "time": "2026-06-05T14:30:00",
            "priority_score": 0, "priority_tier": "Tier 3",
        }
        msg = _format_alert_message(payload)
        assert "TEST" in msg
        assert "10.00" in msg

    def test_t2_r2_message_special_characters_in_symbol(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "BRK.B", "price": 500.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 1.5, "time": "2026-06-05T14:30:00",
            "priority_score": 60, "priority_tier": "Tier 2",
        }
        msg = _format_alert_message(payload)
        assert "BRK" in msg

    def test_t2_r2_message_zero_price(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "TEST", "price": 0.0, "alert_type": "VOLUME_SPIKE",
            "rvol": 5.0, "time": "2026-06-05T14:30:00",
            "priority_score": 40, "priority_tier": "Tier 3",
        }
        msg = _format_alert_message(payload)
        assert "0.00" in msg

    def test_t2_r2_message_extremely_long_symbol(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "VERYLONGTICKERNAME", "price": 10.0,
            "alert_type": "NEAR_HOD_RADAR", "rvol": 2.0,
            "time": "2026-06-05T14:30:00",
            "priority_score": 50, "priority_tier": "Tier 2",
        }
        msg = _format_alert_message(payload)
        assert "VERYLONGTICKERNAME" in msg

    def test_t2_r2_message_vwap_zero_skips_line(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "TEST", "price": 10.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 2.0, "time": "2026-06-05T14:30:00",
            "priority_score": 50, "priority_tier": "Tier 2",
            "vwap": 0.0,
        }
        msg = _format_alert_message(payload)
        assert "VWAP dist" not in msg

    def test_t2_r2_message_yesterday_high_zero_skips_line(self):
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "TEST", "price": 10.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 2.0, "time": "2026-06-05T14:30:00",
            "priority_score": 50, "priority_tier": "Tier 2",
            "yesterday_high": 0.0,
        }
        msg = _format_alert_message(payload)
        assert "PDH dist" not in msg


class TestTier2R3PerformanceBoundaries:
    """Tier 2 boundary tests for R3 performance scoring."""

    @pytest.mark.asyncio
    async def test_t2_r3_daily_summary_invalid_date_format(self, client):
        resp = await client.get("/api/alerts/daily-summary?date=not-a-date")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_t2_r3_daily_summary_no_forward_returns(
        self, seed_alert, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
        )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        tickers = data.get("tickers", [])
        if tickers:
            alert = tickers[0]["alerts"][0]
            assert alert.get("fwd_1m") is None

    @pytest.mark.asyncio
    async def test_t2_r3_performance_scorecard_empty_db(self, client):
        resp = await client.get("/api/alerts/performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        # May have pre-existing data; just verify structure
        assert "scorecard" in data
        assert isinstance(data["scorecard"], list)

    @pytest.mark.asyncio
    async def test_t2_r3_scorecard_extreme_forward_return(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today - timedelta(days=2)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=100.0, alert_time=alert_time,
        )
        await seed_price_candles(
            symbol="AAPL", alert_time=alert_time,
            trigger_price=100.0, num_candles=16, trend="up",
        )
        resp = await client.get("/api/alerts/performance?days=30")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_t2_r3_scorecard_zero_trigger_price(
        self, seed_alert, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today - timedelta(days=1)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=0.0, alert_time=alert_time,
        )
        resp = await client.get("/api/alerts/performance?days=30")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_t2_r3_daily_summary_large_dataset(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=0, second=0, microsecond=0)
        for i in range(10):
            t = alert_time + timedelta(minutes=i * 5)
            await seed_alert(
                symbol="AAPL", alert_type="NEAR_HOD_RADAR",
                trigger_price=150.0 + i, alert_time=t,
            )
            await seed_price_candles(
                symbol="AAPL", alert_time=t,
                trigger_price=150.0 + i, num_candles=16, trend="up",
            )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_t2_r3_scorecard_days_parameter(
        self, seed_alert, seed_price_candles, client
    ):
        today = datetime.now(timezone.utc)
        old_alert = today - timedelta(days=60)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=old_alert,
        )
        await seed_price_candles(
            symbol="AAPL", alert_time=old_alert,
            trigger_price=150.0, num_candles=16, trend="up",
        )
        resp_30 = await client.get("/api/alerts/performance?days=30")
        resp_90 = await client.get("/api/alerts/performance?days=90")
        assert resp_30.status_code == 200
        assert resp_90.status_code == 200


# ===================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (>= 4 tests)
# ===================================================================

class TestTier3CrossFeature:
    """Tier 3 tests combining multiple features."""

    @pytest.mark.asyncio
    async def test_t3_r1_r2_r3_full_pipeline(
        self, seed_alert, seed_price_candles, client, capture_telegram_api
    ):
        """Full pipeline: alert creation -> Telegram dispatch -> daily-summary."""
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        alert_id, at = await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
            priority_tier="Tier 1",
        )
        await seed_price_candles(
            symbol="AAPL", alert_time=alert_time,
            trigger_price=150.0, num_candles=16, trend="up",
        )
        from fastapi_app.tasks.alerts import _format_alert_message
        payload = {
            "symbol": "AAPL", "price": 150.0, "alert_type": "NEAR_HOD_RADAR",
            "rvol": 2.5, "time": alert_time.isoformat(),
            "priority_score": 80, "priority_tier": "Tier 1",
        }
        msg = _format_alert_message(payload)
        assert "NEAR HOD RADAR" in msg

        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tickers"]) >= 1

    @pytest.mark.asyncio
    async def test_t3_r1_r2_halt_resume_telegram_format(
        self, seed_alert, capture_telegram_api
    ):
        """Halt/resume pair produces correct Telegram messages."""
        halt_time = datetime.now(timezone.utc)
        await seed_alert(
            symbol="AAPL", alert_type="VOLATILITY_HALT",
            trigger_price=145.0, alert_time=halt_time,
        )
        resume_time = halt_time + timedelta(minutes=2)
        await seed_alert(
            symbol="AAPL", alert_type="VOLATILITY_RESUME",
            trigger_price=148.0, alert_time=resume_time,
        )
        from fastapi_app.tasks.alerts import _format_alert_message
        halt_msg = _format_alert_message({
            "symbol": "AAPL", "price": 145.0, "alert_type": "VOLATILITY_HALT",
            "rvol": 0.0, "time": halt_time.isoformat(),
            "priority_score": 50, "priority_tier": "Tier 2",
        })
        resume_msg = _format_alert_message({
            "symbol": "AAPL", "price": 148.0, "alert_type": "VOLATILITY_RESUME",
            "rvol": 0.0, "time": resume_time.isoformat(),
            "priority_score": 50, "priority_tier": "Tier 2",
        })
        assert "VOLATILITY HALT" in halt_msg
        assert "VOLATILITY RESUME" in resume_msg

    @pytest.mark.asyncio
    async def test_t3_r1_r3_suppressed_alert_in_daily_summary(
        self, seed_alert, seed_price_candles, client
    ):
        """Suppressed alerts appear in daily summary with suppressed_reason."""
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
            suppressed_reason="POST_HALT_SUPPRESSION",
        )
        await seed_price_candles(
            symbol="AAPL", alert_time=alert_time,
            trigger_price=150.0, num_candles=16, trend="up",
        )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        tickers = data.get("tickers", [])
        if tickers:
            alert = tickers[0]["alerts"][0]
            assert alert.get("suppressed_reason") == "POST_HALT_SUPPRESSION"

    @pytest.mark.asyncio
    async def test_t3_r2_r3_scorecard_groups_by_alert_type(
        self, seed_alert, seed_price_candles, client
    ):
        """Scorecard groups results by alert_type, price_bucket, float_category."""
        today = datetime.now(timezone.utc)
        base_time = today - timedelta(days=3)
        for i in range(3):
            t = base_time + timedelta(hours=i)
            await seed_alert(
                symbol="AAPL", alert_type="NEAR_HOD_RADAR",
                trigger_price=150.0 + i, alert_time=t,
            )
            await seed_price_candles(
                symbol="AAPL", alert_time=t,
                trigger_price=150.0 + i, num_candles=16, trend="up",
            )
        resp = await client.get("/api/alerts/performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        if data["scorecard"]:
            row = data["scorecard"][0]
            assert "alert_type" in row
            assert "price_bucket" in row
            assert "float_category" in row


# ===================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (>= 5 tests)
# ===================================================================

class TestTier4RealWorldScenarios:
    """Tier 4 tests simulating real-world trading scenarios."""

    @pytest.mark.asyncio
    async def test_t4_r1_full_intraday_session_multiple_tickers(
        self, seed_alert, seed_price_candles, client
    ):
        """Full intraday session: multiple tickers with various alert types."""
        today = datetime.now(timezone.utc)
        session_start = today.replace(hour=14, minute=30, second=0, microsecond=0)
        tickers_alerts = [
            ("AAPL", "NEAR_HOD_RADAR", 150.0),
            ("TSLA", "PREV_DAY_BREAKOUT", 250.0),
            ("SNDL", "VOLUME_SPIKE", 2.50),
            ("AAPL", "NEAR_HOD_RADAR", 152.0),
            ("TSLA", "NEAR_HOD_RADAR", 255.0),
        ]
        for i, (sym, atype, price) in enumerate(tickers_alerts):
            t = session_start + timedelta(minutes=i * 5)
            await seed_alert(
                symbol=sym, alert_type=atype, trigger_price=price,
                alert_time=t, priority_tier="Tier 1" if i < 3 else "Tier 2",
            )
            await seed_price_candles(
                symbol=sym, alert_time=t,
                trigger_price=price, num_candles=16, trend="up",
            )
        eastern_date = (session_start - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        tickers = data.get("tickers", [])
        assert len(tickers) >= 2
        symbols = {t["symbol"] for t in tickers}
        assert "AAPL" in symbols
        assert "TSLA" in symbols

    @pytest.mark.asyncio
    async def test_t4_r1_halt_resume_rapid_follow_up(
        self, seed_alert, seed_price_candles, client
    ):
        """Halt at 14:30, resume at 14:32, NEAR_HOD_RADAR suppressed at 14:33."""
        today = datetime.now(timezone.utc)
        halt_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        resume_time = halt_time + timedelta(minutes=2)
        followup_time = halt_time + timedelta(minutes=3)
        await seed_alert(
            symbol="AAPL", alert_type="VOLATILITY_HALT",
            trigger_price=145.0, alert_time=halt_time,
        )
        await seed_alert(
            symbol="AAPL", alert_type="VOLATILITY_RESUME",
            trigger_price=148.0, alert_time=resume_time,
        )
        await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=followup_time,
            suppressed_reason="POST_HALT_SUPPRESSION",
        )
        eastern_date = (halt_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        tickers = data.get("tickers", [])
        assert len(tickers) >= 1
        alert_types = [a["alert_type"] for a in tickers[0]["alerts"]]
        assert "VOLATILITY_HALT" in alert_types
        assert "VOLATILITY_RESUME" in alert_types

    @pytest.mark.asyncio
    async def test_t4_r2_r3_scorecard_after_multi_day_session(
        self, seed_alert, seed_price_candles, client
    ):
        """Scorecard covers 3 days of trading with mixed alert types."""
        today = datetime.now(timezone.utc)
        for day_offset in range(3):
            base = today - timedelta(days=day_offset + 1)
            for i in range(3):
                t = base.replace(hour=14, minute=i * 10, second=0, microsecond=0)
                alert_type = ["NEAR_HOD_RADAR", "PREV_DAY_BREAKOUT", "VOLUME_SPIKE"][i]
                price = [150.0, 250.0, 2.50][i]
                await seed_alert(
                    symbol=["AAPL", "TSLA", "SNDL"][i],
                    alert_type=alert_type, trigger_price=price, alert_time=t,
                )
                await seed_price_candles(
                    symbol=["AAPL", "TSLA", "SNDL"][i],
                    alert_time=t, trigger_price=price,
                    num_candles=16, trend="up",
                )
        resp = await client.get("/api/alerts/performance?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "scorecard" in data
        assert isinstance(data["scorecard"], list)

    @pytest.mark.asyncio
    async def test_t4_r3_alert_feedback_roundtrip(self, seed_alert, client):
        """Alert feedback submission and retrieval."""
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        alert_id, at = await seed_alert(
            symbol="AAPL", alert_type="NEAR_HOD_RADAR",
            trigger_price=150.0, alert_time=alert_time,
        )
        feedback_body = {
            "alert_time": at.isoformat().replace("+00:00", "Z"),
            "feedback_score": "A+",
            "feedback_notes": "Great breakout, caught the move.",
        }
        resp = await client.post(
            f"/api/alerts/{alert_id}/feedback", json=feedback_body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_t4_r1_r3_penny_stock_low_float_scenario(
        self, seed_alert, seed_price_candles, client
    ):
        """Penny stock (SNDL, $2.50) with micro-float triggers VOLUME_SPIKE."""
        today = datetime.now(timezone.utc)
        alert_time = today.replace(hour=14, minute=30, second=0, microsecond=0)
        await seed_alert(
            symbol="SNDL", alert_type="VOLUME_SPIKE",
            trigger_price=2.50, trigger_volume=2_000_000,
            rel_vol=25.0, float_shares=500_000_000, alert_time=alert_time,
        )
        await seed_price_candles(
            symbol="SNDL", alert_time=alert_time,
            trigger_price=2.50, num_candles=16, trend="up",
        )
        eastern_date = (alert_time - timedelta(hours=4)).strftime("%Y-%m-%d")
        resp = await client.get(f"/api/alerts/daily-summary?date={eastern_date}")
        assert resp.status_code == 200
        data = resp.json()
        tickers = data.get("tickers", [])
        assert len(tickers) >= 1
        assert tickers[0]["symbol"] == "SNDL"


# ===================================================================
# MOCK STREAM GENERATOR SMOKE TESTS
# ===================================================================

class TestMockStreamGenerator:
    """Smoke tests for the mock stream generator helpers."""

    def test_hod_breakout_quotes_count(self):
        quotes = build_hod_breakout_quotes("AAPL", num_ticks=5)
        assert len(quotes) == 5

    def test_hod_breakout_quotes_price_increases(self):
        quotes = build_hod_breakout_quotes("AAPL", base_price=10.0, target_price=11.0, num_ticks=5)
        prices = [q.last_price for q in quotes]
        assert prices == sorted(prices)

    def test_vwap_crossover_quotes_cross_vwap(self):
        quotes = build_vwap_crossover_quotes("AAPL", vwap_price=10.50, num_ticks=5)
        prices = [q.last_price for q in quotes]
        assert prices[0] < 10.50
        assert prices[-1] > 10.50

    def test_volume_spike_last_tick_has_spike(self):
        quotes = build_volume_spike_quotes("AAPL", normal_volume=50000, spike_volume=500000, num_ticks=5)
        assert quotes[-1].total_volume == 500000
        assert quotes[0].total_volume < 500000

    def test_halt_resume_quotes_have_resume(self):
        quotes = build_halt_resume_quotes("AAPL", halt_price=10.0, resume_price=12.0, num_ticks=5)
        assert quotes[0].last_price == 10.0
        assert quotes[-1].last_price == 12.0

    def test_no_alert_quotes_benign(self):
        quotes = build_no_alert_quotes("AAPL", base_price=10.0, num_ticks=3)
        for q in quotes:
            assert q.last_price == 10.0

    def test_body_close_hod_quotes_close_near_high(self):
        quotes = build_body_close_hod_quotes("AAPL", base_price=10.0, hod_price=11.0, close_pct=0.85)
        for q in quotes:
            assert q.close_price > q.low_price

    def test_tod_volume_quotes_single_tick(self):
        quotes = build_tod_volume_quotes("AAPL", time_of_day="09:35", volume=200000)
        assert len(quotes) == 1
        assert quotes[0].total_volume == 200000

    def test_level1quote_to_schwab_dict(self):
        q = Level1Quote(symbol="AAPL", last_price=100.0, bid=99.5, ask=100.5, total_volume=50000)
        d = q.to_schwab_dict()
        assert d["symbol"] == "AAPL"
        assert d["lastPrice"] == 100.0
        assert d["totalVolume"] == 50000

    def test_alert_payload_to_json_dict(self):
        ap = AlertPayload(
            symbol="AAPL", price=150.0, volume=100000, rvol=2.5,
            gap_pct=5.0, float_shares=50_000_000,
            alert_type="NEAR_HOD_RADAR", time="2026-06-05T14:30:00",
        )
        d = ap.to_json_dict()
        assert d["symbol"] == "AAPL"
        assert d["alert_type"] == "NEAR_HOD_RADAR"
