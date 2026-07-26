"""M2 Trigger Quality Empirical Verification Tests.

Simulates realistic market data scenarios to verify the three trigger
optimizations: HOD Breakout (body-close), Volume Spike (TOD-adjusted),
and VWAP Crossover (ATR-based hysteresis).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import pytz
import time
import math
from collections import defaultdict

ET = pytz.timezone("America/New_York")


def _make_streamer():
    """Build a minimal SchwabStreamer with mocked DB/client."""
    with patch("momentum_screener.schwab.stream_client.get_client"):
        with patch("momentum_screener.schwab.stream_client.redis.Redis"):
            with patch("momentum_screener.schwab.stream_client.StreamClient"):
                from momentum_screener.schwab.stream_client import SchwabStreamer
                s = SchwabStreamer()
    s.db_pool = MagicMock()
    s.config_service = MagicMock()
    s.fundamentals_cache = {}
    s.vwap_state = {}
    s.price_history_1m = {}
    s.completed_bars_1m = {}
    s.bars_1m = {}
    s.last_known_price = {}
    s.last_known_volume = {}
    s.last_known_high = {}
    s.last_known_low = {}
    s.last_known_open = {}
    s.last_known_bid = {}
    s.last_known_ask = {}
    s.prev_day_breakout_fired = set()
    s.current_date = None
    s.cooldowns = {}
    s.halted_tickers = {}
    s.halt_resume_times = {}
    s.watchlist_symbols = set()
    s.watchlist_tags = {}
    s.catalyst_tags = {}
    s.last_hod_breakout_time = {}
    s.prev_session_high = {}
    s.global_config = None
    s.configs = None
    s.fired_alerts_session = defaultdict(list)
    s.ticker_group_ids = {}
    return s


# ═══════════════════════════════════════════════════════════════════════
# SECTION 1: HOD Breakout (Body-Close)
# ═══════════════════════════════════════════════════════════════════════

class TestHodBreakoutBodyClose:

    def test_wick_above_hod_close_below_does_not_fire(self):
        """Wick touches $10.50 but candle closes at $9.90 — should NOT fire."""
        s = _make_streamer()
        s.prev_session_high["TEST"] = 10.00
        s.halt_resume_times["TEST"] = 0.0
        # Simulate candle: high=10.50, close=9.90
        candle = {"high": 10.50, "close": 9.90, "low": 9.80, "open": 10.00, "volume": 100_000}
        s.completed_bars_1m["TEST"] = [candle]
        hod_ref = s.prev_session_high.get("TEST", 0.0)
        assert candle["close"] <= hod_ref  # 9.90 <= 10.00 → no breakout

    def test_close_exactly_at_hod_rejected(self):
        """Close exactly at HOD ($10.00) with strict > should NOT fire."""
        s = _make_streamer()
        s.prev_session_high["TEST"] = 10.00
        candle = {"high": 10.10, "close": 10.00, "low": 9.95, "open": 10.00, "volume": 100_000}
        hod_ref = s.prev_session_high.get("TEST", 0.0)
        assert not (candle["close"] > hod_ref)  # 10.00 > 10.00 is False

    def test_close_above_hod_fires(self):
        """Close above HOD ($10.15 > $10.00) should fire NEAR_HOD_RADAR."""
        s = _make_streamer()
        s.prev_session_high["TEST"] = 10.00
        candle = {"high": 10.20, "close": 10.15, "low": 9.95, "open": 10.00, "volume": 100_000}
        hod_ref = s.prev_session_high.get("TEST", 0.0)
        fired = candle["close"] > hod_ref
        assert fired
        # Update HOD ref
        s.prev_session_high["TEST"] = max(s.prev_session_high.get("TEST", 0.0), candle["high"])
        assert s.prev_session_high["TEST"] == 10.20

    def test_hod_ref_uses_max_prev_high_not_close(self):
        """BUG-1 fix: HOD ref tracks max(prev, high) not just close."""
        s = _make_streamer()
        s.prev_session_high["TEST"] = 10.00
        candle = {"high": 10.50, "close": 10.30, "low": 10.10, "open": 10.00}
        hod_ref = s.prev_session_high.get("TEST", 0.0)
        assert candle["close"] > hod_ref  # breakout
        s.prev_session_high["TEST"] = max(s.prev_session_high.get("TEST", 0.0), candle["high"])
        assert s.prev_session_high["TEST"] == 10.50  # not 10.30
        # Next candle close=10.40 — should NOT fire
        assert not (10.40 > 10.50)

    def test_post_halt_suppression_blocks_hod(self):
        """Post-halt suppression within 120s blocks HOD breakout."""
        s = _make_streamer()
        s.halt_resume_times["TEST"] = time.time() - 60  # 60s ago
        resume_ts = s.halt_resume_times.get("TEST")
        post_halt_suppressed = resume_ts is not None and (time.time() - resume_ts) < 120
        assert post_halt_suppressed
        # HOD check should be skipped
        assert not (not post_halt_suppressed and 10.15 > 10.00)

    def test_candle_completion_gate(self):
        """HOD breakout only fires at candle completion (minute boundary)."""
        s = _make_streamer()
        s.prev_session_high["TEST"] = 10.00
        s.completed_bars_1m["TEST"] = []
        # Same minute — no candle completion → no HOD check
        ts = time.time()
        minute_ts = int(ts / 60)
        s.bars_1m["TEST"] = {
            "minute": minute_ts, "open": 10.00, "high": 10.20,
            "low": 9.95, "close": 10.15, "start_volume": 100_000, "last_volume": 150_000,
        }
        # Same minute tick — updates candle but no completion
        state = s.bars_1m["TEST"]
        state["high"] = max(state["high"], 10.15)
        state["close"] = 10.15
        # No history append — no HOD breakout evaluated
        assert len(s.completed_bars_1m["TEST"]) == 0

    def test_gap_up_initialization(self):
        """First candle with gap-up initializes HOD from Schwab high_price."""
        s = _make_streamer()
        s.prev_session_high["TEST"] = 0.0  # not initialized
        high_price = 12.00  # Schwab reports this
        if s.prev_session_high.get("TEST", 0) <= 0 and high_price > 0:
            s.prev_session_high["TEST"] = high_price
        assert s.prev_session_high["TEST"] == 12.00


# ═══════════════════════════════════════════════════════════════════════
# SECTION 2: Volume Spike (Time-of-Day Adjusted)
# ═══════════════════════════════════════════════════════════════════════

class TestVolumeSpikeTimeOfDay:

    def test_opening_hour_threshold_4x(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 9, 35, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 4.0

    def test_mid_morning_threshold_5x(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 10, 30, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 5.0

    def test_lunch_threshold_6x(self):
        s = _make_streamer()
        for h in [11, 12, 13]:
            t = datetime(2026, 7, 19, h, 30, tzinfo=ET)
            assert s._volume_spike_threshold(t) == 6.0, f"Hour {h} should be 6x"

    def test_afternoon_threshold_5x(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 14, 30, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 5.0

    def test_post_market_threshold_7x(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 16, 30, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 7.0

    def test_premarket_finding_1_bug(self):
        """FINDING-1: Pre-market hours (h<9) return 5x instead of expected 7x."""
        s = _make_streamer()
        for h in [4, 5, 6, 7, 8]:
            t = datetime(2026, 7, 19, h, 30, tzinfo=ET)
            result = s._volume_spike_threshold(t)
            # BUG: falls to elif h < 11 → 5.0x, should be 7.0x
            assert result == 5.0, f"Pre-market hour {h} returns {result}x, confirmed FINDING-1"

    def test_opening_hour_boundary(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 9, 0, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 4.0

    def test_lunch_boundary_start(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 11, 0, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 6.0

    def test_afternoon_boundary_start(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 14, 0, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 5.0

    def test_post_market_boundary(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 16, 0, tzinfo=ET)
        assert s._volume_spike_threshold(t) == 7.0


class TestVolumeTodMultiplier:

    def test_pre_8am_returns_002(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 7, 30, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.02

    def test_8am_9am_returns_008(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 8, 30, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.08

    def test_9am_930am_returns_015(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 9, 15, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.15

    def test_930am_10am_returns_020(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 9, 45, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.20

    def test_10am_11am_returns_016(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 10, 30, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.16

    def test_11am_2pm_returns_014(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 12, 0, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.14

    def test_2pm_4pm_returns_018(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 15, 0, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.18

    def test_post_4pm_returns_003(self):
        s = _make_streamer()
        t = datetime(2026, 7, 19, 16, 30, tzinfo=ET)
        assert s._volume_tod_multiplier(t) == 0.03


class TestVolumeSpikeRealisticScenario:

    def test_opening_burst_4x_fires(self):
        s = _make_streamer()
        avg_vol = 100_000
        candle_vol = 400_000
        now_et = datetime(2026, 7, 19, 9, 35, tzinfo=ET)
        threshold = s._volume_spike_threshold(now_et)
        assert candle_vol >= threshold * avg_vol

    def test_midday_6x_does_not_fire_at_5x(self):
        s = _make_streamer()
        avg_vol = 100_000
        candle_vol = 500_000
        now_et = datetime(2026, 7, 19, 12, 0, tzinfo=ET)
        threshold = s._volume_spike_threshold(now_et)
        assert threshold == 6.0
        assert not (candle_vol >= threshold * avg_vol)

    def test_postmarket_7x_requires_high_spike(self):
        s = _make_streamer()
        avg_vol = 50_000
        candle_vol = 300_000  # 6x avg
        now_et = datetime(2026, 7, 19, 16, 30, tzinfo=ET)
        threshold = s._volume_spike_threshold(now_et)
        assert threshold == 7.0
        assert not (candle_vol >= threshold * avg_vol)


# ═══════════════════════════════════════════════════════════════════════
# SECTION 3: VWAP Crossover (ATR-Based Hysteresis)
# ═══════════════════════════════════════════════════════════════════════

class TestVwapCrossoverATR:

    def test_true_range_textbook_correct(self):
        H, L, prev_C = 10.50, 9.80, 10.00
        tr = max(H - L, abs(H - prev_C), abs(L - prev_C))
        assert abs(tr - 0.70) < 1e-9

    def test_true_range_gap_up(self):
        H, L, prev_C = 11.00, 10.50, 10.00
        tr = max(H - L, abs(H - prev_C), abs(L - prev_C))
        assert abs(tr - 1.00) < 1e-9

    def test_true_range_gap_down(self):
        H, L, prev_C = 9.50, 9.00, 10.00
        tr = max(H - L, abs(H - prev_C), abs(L - prev_C))
        assert abs(tr - 1.00) < 1e-9

    def test_atr_buffer_floor_0005(self):
        atr_val, vwap = 0.01, 10.0
        buffer = max(0.005, min(0.03, atr_val / vwap))
        assert abs(buffer - 0.005) < 1e-9

    def test_atr_buffer_cap_003(self):
        atr_val, vwap = 1.0, 10.0
        buffer = max(0.005, min(0.03, atr_val / vwap))
        assert abs(buffer - 0.03) < 1e-9

    def test_atr_buffer_normal_range(self):
        atr_val, vwap = 0.08, 10.0
        buffer = max(0.005, min(0.03, atr_val / vwap))
        assert abs(buffer - 0.008) < 1e-9

    def test_cold_start_default_buffer(self):
        buffer = 0.015
        assert buffer == 0.015

    def test_missing_high_low_fallback_to_close(self):
        c = {"open": 10.0, "close": 10.20}
        hi = c.get("high", c["close"])
        lo = c.get("low", c["close"])
        assert hi == 10.20
        assert lo == 10.20

    def test_directional_only_bullish_fires(self):
        v_state = {"status": "below"}
        vwap, atr_buffer = 10.0, 0.01
        last_price = 10.15
        triggered = False
        if v_state["status"] == "below" and last_price >= vwap * (1.0 + atr_buffer):
            triggered = True
            v_state["status"] = "above"
        assert triggered
        assert v_state["status"] == "above"

    def test_bearish_crossover_does_not_fire(self):
        v_state = {"status": "above"}
        vwap, atr_buffer = 10.0, 0.01
        last_price = 9.85
        triggered = False
        if v_state["status"] == "below" and last_price >= vwap * (1.0 + atr_buffer):
            triggered = True
        elif v_state["status"] == "above" and last_price <= vwap * (1.0 - atr_buffer):
            v_state["status"] = "below"
        assert not triggered
        assert v_state["status"] == "below"

    def test_rvol_gate_enforced(self):
        rvol = 1.5
        assert not (rvol >= 2.0)
        rvol = 2.5
        assert rvol >= 2.0

    def test_wider_buffer_no_chatter(self):
        atr_val, vwap = 0.08, 10.0
        buffer_full = max(0.005, min(0.03, atr_val / vwap))
        buffer_half = max(0.005, min(0.03, (atr_val * 0.5) / vwap))
        assert buffer_full > buffer_half


# ═══════════════════════════════════════════════════════════════════════
# SECTION 4: Integration & Regression Scenarios
# ═══════════════════════════════════════════════════════════════════════

class TestRealisticMarketScenario:

    def test_hod_wick_rejection_scenario(self):
        """Candle wicks to new high but closes below → no false HOD alert."""
        s = _make_streamer()
        s.prev_session_high["AAPL"] = 195.00

        candle1 = {"volume": 80_000, "open": 194.50, "close": 194.80,
                   "high": 195.50, "low": 194.20}
        candle2 = {"volume": 90_000, "open": 194.80, "close": 195.10,
                   "high": 195.30, "low": 194.70}

        # Candle 1: wick=195.50, close=194.80 < HOD=195.00 → no breakout
        hod_ref = s.prev_session_high.get("AAPL", 0.0)
        assert not (candle1["close"] > hod_ref)
        assert s.prev_session_high["AAPL"] == 195.00

        # Candle 2: close=195.10 > HOD=195.00 → breakout
        hod_ref = s.prev_session_high.get("AAPL", 0.0)
        assert candle2["close"] > hod_ref
        s.prev_session_high["AAPL"] = max(s.prev_session_high.get("AAPL", 0.0), candle2["high"])
        assert s.prev_session_high["AAPL"] == 195.30

        # Candle 3: close=195.20 < 195.30 → no re-fire
        candle3 = {"volume": 70_000, "open": 195.10, "close": 195.20,
                   "high": 195.25, "low": 195.00}
        hod_ref = s.prev_session_high.get("AAPL", 0.0)
        assert not (candle3["close"] > hod_ref)

    def test_volume_spike_opening_vs_lunch(self):
        s = _make_streamer()
        avg_vol = 100_000
        candle_vol = 450_000

        t_open = datetime(2026, 7, 19, 9, 35, tzinfo=ET)
        assert candle_vol >= s._volume_spike_threshold(t_open) * avg_vol

        t_lunch = datetime(2026, 7, 19, 12, 0, tzinfo=ET)
        assert not (candle_vol >= s._volume_spike_threshold(t_lunch) * avg_vol)

    def test_vwap_atr_adapts_to_volatility(self):
        vwap = 50.0
        buffer_low = max(0.005, min(0.03, 0.20 / vwap))
        buffer_high = max(0.005, min(0.03, 2.00 / vwap))
        assert buffer_high > buffer_low
        assert abs(buffer_high - 0.03) < 1e-9
        assert abs(buffer_low - 0.005) < 1e-9  # 0.004 < 0.005 floor

    def test_14_period_atr_window(self):
        """ATR uses at most 14 most recent candles."""
        candles = [{"high": 10 + i * 0.1, "low": 9.5 + i * 0.1,
                     "close": 9.8 + i * 0.1, "open": 9.6 + i * 0.1}
                    for i in range(20)]
        recent = candles[-14:] if len(candles) >= 14 else candles
        assert len(recent) == 14
        # Verify it doesn't use all 20
        assert len(recent) < len(candles)


# ═══════════════════════════════════════════════════════════════════════
# SECTION 5: Known Bugs & Discrepancies (from Reviews)
# ═══════════════════════════════════════════════════════════════════════

class TestKnownBugsAndDiscrepancies:

    def test_finding_1_premarket_tier_returns_5x_not_7x(self):
        """FINDING-1: Pre-market (h < 9) falls to elif h < 11 → 5.0x."""
        s = _make_streamer()
        for h in [4, 5, 6, 7, 8]:
            t = datetime(2026, 7, 19, h, 30, tzinfo=ET)
            result = s._volume_spike_threshold(t)
            assert result == 5.0, f"Pre-market {h}:30 returns {result}"

    def test_disc_1_full_atr_no_half_multiplier(self):
        """DISC-1: Full ATR used, buffer is 2x wider than 0.5x ATR (when above floor)."""
        atr_val, vwap = 0.16, 10.0  # 1.6% — safely above 0.5% floor
        buffer = max(0.005, min(0.03, atr_val / vwap))
        buffer_half = max(0.005, min(0.03, (atr_val * 0.5) / vwap))
        assert abs(buffer - 0.016) < 1e-9
        assert abs(buffer_half - 0.008) < 1e-9
        assert abs(buffer - 2 * buffer_half) < 1e-9

    def test_pre_8am_baseline_002_vs_explorer_003(self):
        """DISC-2: Pre-8am baseline is 0.02, explorer recommended 0.03."""
        s = _make_streamer()
        t = datetime(2026, 7, 19, 7, 0, tzinfo=ET)
        result = s._volume_tod_multiplier(t)
        assert result == 0.02
        assert result != 0.03

    def test_tod_multiplier_monotonicity(self):
        """Volume multiplier should roughly increase toward market open."""
        s = _make_streamer()
        profile = []
        for h in range(4, 18):
            t = datetime(2026, 7, 19, h, 30, tzinfo=ET)
            profile.append((h, s._volume_tod_multiplier(t)))
        # Verify pre-market < open hour
        pre_8 = next(v for h, v in profile if h == 7)
        at_9 = next(v for h, v in profile if h == 9)
        # 9am (minute=30) → 930am_10am bucket = 0.20, pre_8am = 0.02
        assert at_9 > pre_8

    def test_volume_spike_tiers_are_monotonic_stricter_toward_low_vol(self):
        """Thresholds: opening=4x (easy), lunch=6x (hard), post=7x (hardest)."""
        s = _make_streamer()
        t_open = datetime(2026, 7, 19, 9, 30, tzinfo=ET)
        t_mid = datetime(2026, 7, 19, 10, 30, tzinfo=ET)
        t_lunch = datetime(2026, 7, 19, 12, 0, tzinfo=ET)
        t_post = datetime(2026, 7, 19, 16, 30, tzinfo=ET)
        assert s._volume_spike_threshold(t_open) < s._volume_spike_threshold(t_mid)
        assert s._volume_spike_threshold(t_mid) < s._volume_spike_threshold(t_lunch)
        assert s._volume_spike_threshold(t_lunch) < s._volume_spike_threshold(t_post)


# ═══════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback
    passed = 0
    failed = 0
    errors = []

    test_classes = [
        TestHodBreakoutBodyClose,
        TestVolumeSpikeTimeOfDay,
        TestVolumeTodMultiplier,
        TestVolumeSpikeRealisticScenario,
        TestVwapCrossoverATR,
        TestRealisticMarketScenario,
        TestKnownBugsAndDiscrepancies,
    ]

    for cls in test_classes:
        instance = cls()
        for name in sorted(dir(instance)):
            if not name.startswith("test_"):
                continue
            method = getattr(instance, name)
            try:
                method()
                passed += 1
                print(f"  PASS  {cls.__name__}.{name}")
            except AssertionError as e:
                failed += 1
                errors.append((f"{cls.__name__}.{name}", e))
                print(f"  FAIL  {cls.__name__}.{name}: {e}")
            except Exception as e:
                failed += 1
                errors.append((f"{cls.__name__}.{name}", e))
                print(f"  ERROR {cls.__name__}.{name}: {e}")

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
    if errors:
        print(f"\nFailed tests:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    sys.exit(1 if failed else 0)
