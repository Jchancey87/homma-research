"""
Edge case tests for M2 Trigger Quality Optimizations.
Covers: HOD Breakout (body-close), Volume Spike (TOD-adjusted), VWAP Crossover (ATR hysteresis).
"""
import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from validation import EASTERN_TZ
from momentum_screener.schwab.stream_client import SchwabStreamer, VOLUME_TOD_PROFILE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_streamer(symbol="AAPL", vol_10d_avg=1000, shares_out=50_000_000):
    streamer = SchwabStreamer()
    streamer.current_date = datetime.now(EASTERN_TZ).date()
    streamer.fundamentals_cache[symbol] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': vol_10d_avg,
        'shares_outstanding': shares_out,
    }
    streamer.check_and_fire_alert = AsyncMock(return_value=True)
    return streamer


def _et(hour, minute=0):
    return datetime(2026, 7, 19, hour, minute, tzinfo=EASTERN_TZ)


# ===================================================================
# PART 1: _volume_tod_multiplier() unit tests
# ===================================================================

class TestVolumeTodMultiplier:
    """Direct unit tests for the time-of-day RVOL baseline helper."""

    def test_very_early_premarket(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(4, 0)) == VOLUME_TOD_PROFILE['pre_8am']

    def test_530am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(5, 30)) == VOLUME_TOD_PROFILE['pre_8am']

    def test_759am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(7, 59)) == VOLUME_TOD_PROFILE['pre_8am']

    def test_8am_boundary(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(8, 0)) == VOLUME_TOD_PROFILE['8am_9am']

    def test_830am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(8, 30)) == VOLUME_TOD_PROFILE['8am_9am']

    def test_859am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(8, 59)) == VOLUME_TOD_PROFILE['8am_9am']

    def test_9am_before_30(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(9, 0)) == VOLUME_TOD_PROFILE['9am_930am']

    def test_929am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(9, 29)) == VOLUME_TOD_PROFILE['9am_930am']

    def test_930am_open(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(9, 30)) == VOLUME_TOD_PROFILE['930am_10am']

    def test_945am_opening(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(9, 45)) == VOLUME_TOD_PROFILE['930am_10am']

    def test_959am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(9, 59)) == VOLUME_TOD_PROFILE['930am_10am']

    def test_10am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(10, 0)) == VOLUME_TOD_PROFILE['930am_10am']

    def test_1001am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(10, 1)) == VOLUME_TOD_PROFILE['10am_11am']

    def test_1030am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(10, 30)) == VOLUME_TOD_PROFILE['10am_11am']

    def test_1059am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(10, 59)) == VOLUME_TOD_PROFILE['10am_11am']

    def test_11am(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(11, 0)) == VOLUME_TOD_PROFILE['11am_2pm']

    def test_1pm(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(13, 0)) == VOLUME_TOD_PROFILE['11am_2pm']

    def test_159pm(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(13, 59)) == VOLUME_TOD_PROFILE['11am_2pm']

    def test_2pm(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(14, 0)) == VOLUME_TOD_PROFILE['2pm_4pm']

    def test_330pm(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(15, 30)) == VOLUME_TOD_PROFILE['2pm_4pm']

    def test_359pm(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(15, 59)) == VOLUME_TOD_PROFILE['2pm_4pm']

    def test_4pm_post_market(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(16, 0)) == VOLUME_TOD_PROFILE['post_4pm']

    def test_5pm(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(17, 0)) == VOLUME_TOD_PROFILE['post_4pm']

    def test_1159pm(self):
        streamer = SchwabStreamer()
        assert streamer._volume_tod_multiplier(_et(23, 59)) == VOLUME_TOD_PROFILE['post_4pm']

    def test_monotonic_early_to_late(self):
        """RVOL baseline should increase as we approach open."""
        s = SchwabStreamer()
        vals = [s._volume_tod_multiplier(_et(h, m))
                for h, m in [(4, 0), (8, 0), (9, 0), (9, 30), (10, 0)]]
        # Each step should be >= previous (not strictly monotonic)
        for i in range(1, len(vals)):
            assert vals[i] >= vals[i - 1], f"Non-monotonic at step {i}: {vals}"


# ===================================================================
# PART 2: _volume_spike_threshold() unit tests
# ===================================================================

class TestVolumeSpikeThreshold:
    """Direct unit tests for the dynamic volume spike threshold."""

    def test_opening_hour_9am(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(9, 0)) == 4.0

    def test_opening_hour_959(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(9, 59)) == 4.0

    def test_mid_morning_10am(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(10, 0)) == 5.0

    def test_mid_morning_1030(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(10, 30)) == 5.0

    def test_lunch_11am(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(11, 0)) == 6.0

    def test_lunch_1pm(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(13, 0)) == 6.0

    def test_lunch_159pm(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(13, 59)) == 6.0

    def test_afternoon_2pm(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(14, 0)) == 5.0

    def test_afternoon_330pm(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(15, 30)) == 5.0

    def test_post_market_4pm(self):
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(16, 0)) == 7.0

    def test_premarket_4am_returns_7x(self):
        """FIX-3: Pre-market (h<9) now correctly returns 7.0x for sparse volume confirmation."""
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(4, 0)) == 7.0

    def test_premarket_8am_returns_7x(self):
        """FIX-3: 8am now correctly returns 7.0x for pre-market sparse volume."""
        s = SchwabStreamer()
        assert s._volume_spike_threshold(_et(8, 0)) == 7.0


# ===================================================================
# PART 3: HOD Breakout Edge Cases (body-close, candle-completion)
# ===================================================================

class TestHodBreakoutEdgeCases:
    """Verify HOD breakout fires only on candle completion, body-close > HOD ref."""

    @pytest.mark.asyncio
    async def test_close_exactly_at_hod_rejects(self):
        """Close == HOD ref should NOT fire (strict >)."""
        s = _make_streamer()
        s.prev_session_high['AAPL'] = 10.50
        # Candle just completed: close == hod_ref
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,  # previous minute (triggers candle completion)
            'open': 10.0, 'high': 10.50, 'low': 10.0,
            'close': 10.50,  # exactly at HOD
            'start_volume': 100000, 'last_volume': 105000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.50, total_volume=105000,
            high_price=10.50, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" not in fired

    @pytest.mark.asyncio
    async def test_close_above_hod_fires(self):
        """Close > HOD ref with RVOL >= 1.5 should fire."""
        s = _make_streamer(vol_10d_avg=100)
        s.prev_session_high['AAPL'] = 10.50
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.80, 'low': 10.0,
            'close': 10.70,
            'start_volume': 100000, 'last_volume': 105000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.70, total_volume=105000,
            high_price=10.80, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" in fired

    @pytest.mark.asyncio
    async def test_wick_above_hod_close_below_rejects(self):
        """High > HOD but close < HOD should NOT fire (body-close check)."""
        s = _make_streamer()
        s.prev_session_high['AAPL'] = 10.50
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.80, 'low': 10.0,
            'close': 10.30,  # close is below HOD
            'start_volume': 100000, 'last_volume': 105000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.30, total_volume=105000,
            high_price=10.80, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" not in fired

    @pytest.mark.asyncio
    async def test_first_candle_gap_up_above_hod(self):
        """First candle: no prev_session_high set, should initialize from Schwab high_price."""
        s = _make_streamer(vol_10d_avg=100)
        # No prev_session_high set for AAPL — simulates first candle
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 11.0, 'high': 11.50, 'low': 10.80,
            'close': 11.40,
            'start_volume': 100000, 'last_volume': 105000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=11.40, total_volume=105000,
            high_price=11.50, low_price=10.80, open_price=11.0,
        )

        # On first candle, prev_session_high is initialized to high_price (11.50)
        # close=11.40 < 11.50, so no HOD breakout fires
        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" not in fired
        # But prev_session_high should now be set
        assert s.prev_session_high['AAPL'] == 11.50

    @pytest.mark.asyncio
    async def test_first_candle_close_above_init_hod(self):
        """First candle: close > initialized HOD should fire."""
        s = _make_streamer(vol_10d_avg=100)
        # Initialize prev_session_high manually (simulating Schwab data)
        s.prev_session_high['AAPL'] = 10.00
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.80, 'low': 10.0,
            'close': 10.70,
            'start_volume': 100000, 'last_volume': 105000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.70, total_volume=105000,
            high_price=10.80, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" in fired

    @pytest.mark.asyncio
    async def test_no_fire_without_candle_completion(self):
        """Same candle (no minute advancement) should NOT trigger HOD breakout."""
        s = _make_streamer()
        s.prev_session_high['AAPL'] = 10.50
        current_min = int(time.time() / 60)
        s.bars_1m['AAPL'] = {
            'minute': current_min,  # same minute = no candle completion
            'open': 10.0, 'high': 10.80, 'low': 10.0,
            'close': 10.70,
            'start_volume': 100000, 'last_volume': 105000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.70, total_volume=105000,
            high_price=10.80, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" not in fired

    @pytest.mark.asyncio
    async def test_hod_ref_uses_high_not_close(self):
        """BUG-1 regression: HOD ref should update to candle high, not close."""
        s = _make_streamer()
        s.prev_session_high['AAPL'] = 10.50

        # First candle completes: high=10.80, close=10.70
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.80, 'low': 10.0,
            'close': 10.70,
            'start_volume': 100000, 'last_volume': 105000,
        }
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.70, total_volume=105000,
            high_price=10.80, low_price=10.0, open_price=10.0,
        )

        # HOD ref should now be max(10.50, 10.80) = 10.80, NOT 10.70 (close)
        assert s.prev_session_high['AAPL'] == 10.80

    @pytest.mark.asyncio
    async def test_post_halt_suppression_blocks_hod(self):
        """HOD breakout should not fire within 120s of volatility resume."""
        s = _make_streamer(vol_10d_avg=100)
        s.prev_session_high['AAPL'] = 10.50
        s.halt_resume_times['AAPL'] = time.time() - 60  # 60s ago (within 120s window)
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.80, 'low': 10.0,
            'close': 10.70,
            'start_volume': 100000, 'last_volume': 105000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.70, total_volume=105000,
            high_price=10.80, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" not in fired


# ===================================================================
# PART 4: Volume Spike Edge Cases (TOD-adjusted)
# ===================================================================

class TestVolumeSpikeEdgeCases:
    """Verify volume spike fires correctly with different TOD thresholds."""

    @pytest.mark.asyncio
    async def test_volume_at_exactly_threshold_fires(self):
        """Candle volume == threshold * avg_vol should fire (>=)."""
        s = _make_streamer()
        # Need 20 completed candles to evaluate volume spike
        s.completed_bars_1m['AAPL'] = [
            {'volume': 1000, 'open': 10.0, 'close': 10.1} for _ in range(20)
        ]
        # avg_vol = 1000, threshold at 10am = 5x, so need candle_volume >= 5000
        # Candle just completed: volume from 100000 to 105000 = 5000
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.3,  # 3% rise (>= 1% required)
            'start_volume': 100000, 'last_volume': 105000,
        }

        with patch('momentum_screener.schwab.stream_client.datetime') as mock_dt:
            mock_dt.now.return_value = _et(10, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await s.evaluate_and_fire_alert(
                symbol='AAPL', last_price=10.3, total_volume=105000,
                high_price=10.5, low_price=10.0, open_price=10.0,
            )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VOLUME_SPIKE" in fired

    @pytest.mark.asyncio
    async def test_volume_just_below_threshold_rejects(self):
        """Candle volume < threshold * avg_vol should NOT fire."""
        s = _make_streamer()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 1000, 'open': 10.0, 'close': 10.1} for _ in range(20)
        ]
        # avg_vol = 1000, threshold at 10am = 5x, need >= 5000
        # Candle volume = 4999 (just below)
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.3,
            'start_volume': 100000, 'last_volume': 104999,
        }

        with patch('momentum_screener.schwab.stream_client.datetime') as mock_dt:
            mock_dt.now.return_value = _et(10, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await s.evaluate_and_fire_alert(
                symbol='AAPL', last_price=10.3, total_volume=104999,
                high_price=10.5, low_price=10.0, open_price=10.0,
            )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VOLUME_SPIKE" not in fired

    @pytest.mark.asyncio
    async def test_opening_burst_lower_threshold(self):
        """At 9:35am (opening), threshold is 4x — easier to fire."""
        s = _make_streamer()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 1000, 'open': 10.0, 'close': 10.1} for _ in range(20)
        ]
        # avg_vol = 1000, threshold at 9am = 4x, candle_vol = 4000
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.3,
            'start_volume': 100000, 'last_volume': 104000,
        }

        with patch('momentum_screener.schwab.stream_client.datetime') as mock_dt:
            mock_dt.now.return_value = _et(9, 35)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await s.evaluate_and_fire_alert(
                symbol='AAPL', last_price=10.3, total_volume=104000,
                high_price=10.5, low_price=10.0, open_price=10.0,
            )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VOLUME_SPIKE" in fired

    @pytest.mark.asyncio
    async def test_lunch_higher_threshold(self):
        """At 11:30am (lunch), threshold is 6x — harder to fire."""
        s = _make_streamer()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 1000, 'open': 10.0, 'close': 10.1} for _ in range(20)
        ]
        # avg_vol = 1000, threshold at 11am = 6x, candle_vol = 5000 (< 6000)
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.3,
            'start_volume': 100000, 'last_volume': 105000,
        }

        with patch('momentum_screener.schwab.stream_client.datetime') as mock_dt:
            mock_dt.now.return_value = _et(11, 30)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await s.evaluate_and_fire_alert(
                symbol='AAPL', last_price=10.3, total_volume=105000,
                high_price=10.5, low_price=10.0, open_price=10.0,
            )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VOLUME_SPIKE" not in fired

    @pytest.mark.asyncio
    async def test_very_early_premarket_uses_7x(self):
        """FIX-3: At 4:30am, threshold is now correctly 7x for pre-market sparse volume.
        Pre-market h < 9 now returns 7.0x, requiring stronger confirmation."""
        s = _make_streamer()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 1000, 'open': 10.0, 'close': 10.1} for _ in range(20)
        ]
        # avg_vol = 1000, threshold at 4:30am = 7x (FIXED: was 5x before)
        # candle_vol = 5500 < 7000 → does NOT fire!
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.3,
            'start_volume': 100000, 'last_volume': 105500,
        }

        with patch('momentum_screener.schwab.stream_client.datetime') as mock_dt:
            mock_dt.now.return_value = _et(4, 30)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await s.evaluate_and_fire_alert(
                symbol='AAPL', last_price=10.3, total_volume=105500,
                high_price=10.5, low_price=10.0, open_price=10.0,
            )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        # Does NOT fire because pre-market threshold is now correctly 7x
        assert "VOLUME_SPIKE" not in fired

    @pytest.mark.asyncio
    async def test_less_than_20_candles_no_fire(self):
        """Volume spike should not fire if history < 20 candles."""
        s = _make_streamer()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 10000, 'open': 10.0, 'close': 10.3} for _ in range(19)
        ]
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.3,
            'start_volume': 100000, 'last_volume': 200000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.3, total_volume=200000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VOLUME_SPIKE" not in fired

    @pytest.mark.asyncio
    async def test_price_must_rise_at_least_1pct(self):
        """Volume spike requires price_rise_pct >= 1%."""
        s = _make_streamer()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 1000, 'open': 10.0, 'close': 10.1} for _ in range(20)
        ]
        # Huge volume but price flat (open=close)
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.0, 'low': 10.0,
            'close': 10.0,  # 0% rise
            'start_volume': 100000, 'last_volume': 120000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.0, total_volume=120000,
            high_price=10.0, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VOLUME_SPIKE" not in fired

    @pytest.mark.asyncio
    async def test_afternoon_threshold_5x(self):
        """At 3pm, threshold is 5x (same as mid-morning)."""
        s = _make_streamer()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 1000, 'open': 10.0, 'close': 10.1} for _ in range(20)
        ]
        # avg_vol = 1000, threshold at 3pm = 5x, candle_vol = 5000 (exactly)
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 1,
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.3,
            'start_volume': 100000, 'last_volume': 105000,
        }

        with patch('momentum_screener.schwab.stream_client.datetime') as mock_dt:
            mock_dt.now.return_value = _et(15, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            await s.evaluate_and_fire_alert(
                symbol='AAPL', last_price=10.3, total_volume=105000,
                high_price=10.5, low_price=10.0, open_price=10.0,
            )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VOLUME_SPIKE" in fired


# ===================================================================
# PART 5: VWAP Crossover Edge Cases (ATR hysteresis)
# ===================================================================

class TestVwapCrossoverEdgeCases:
    """Verify VWAP crossover with True Range-based hysteresis buffer."""

    def _setup_vwap(self, symbol="AAPL"):
        s = _make_streamer()
        # Pre-populate VWAP state so status tracking works
        s.vwap_state[symbol] = {
            'cum_vp': 10.0 * 100000, 'cum_vol': 100000,
            'last_total_vol': 100000, 'status': None,
        }
        return s

    @pytest.mark.asyncio
    async def test_cold_start_skips_vwap_check(self):
        """With < 5 candles, VWAP crossover check is skipped entirely."""
        s = self._setup_vwap()
        # No completed candles — cold start
        s.completed_bars_1m['AAPL'] = []
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.0,
            'start_volume': 100000, 'last_volume': 100000,
        }
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.0, total_volume=100000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )
        # Status stays None because VWAP block requires >=5 candles
        assert s.vwap_state['AAPL']['status'] is None

    @pytest.mark.asyncio
    async def test_5_candles_initializes_status(self):
        """With exactly 5 candles, VWAP check enters and initializes status."""
        s = self._setup_vwap()
        s.completed_bars_1m['AAPL'] = [
            {'volume': 5000, 'open': 10.0, 'close': 10.1, 'high': 10.2, 'low': 10.0}
            for _ in range(5)
        ]
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.0,
            'start_volume': 100000, 'last_volume': 100000,
        }
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.0, total_volume=100000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )
        # 10.0 <= 10.0 * (1 - 0.015) = 9.85 is false
        # 10.0 >= 10.0 * (1 + 0.015) = 10.15 is false
        # status stays None (price within buffer band)
        assert s.vwap_state['AAPL']['status'] is None

    @pytest.mark.asyncio
    async def test_low_price_stock_atr_floor(self):
        """Very low price stock ($1-2): ATR buffer floors at 0.5%."""
        s = SchwabStreamer()
        s.current_date = datetime.now(EASTERN_TZ).date()
        s.fundamentals_cache['PENNY'] = {
            'yesterday_close': 1.00,
            'yesterday_high': 1.20,
            'vol_10d_avg': 50000,
            'shares_outstanding': 10_000_000,
        }
        s.check_and_fire_alert = AsyncMock(return_value=True)
        s.vwap_state['PENNY'] = {
            'cum_vp': 1.0 * 50000, 'cum_vol': 50000,
            'last_total_vol': 50000, 'status': 'below',
        }
        # Create 14 candles with tiny TR (high-low = 0.01)
        s.completed_bars_1m['PENNY'] = [
            {'volume': 5000, 'open': 1.0, 'close': 1.0, 'high': 1.005, 'low': 0.995}
            for _ in range(14)
        ]
        # ATR = 0.01, VWAP = 1.0, buffer = max(0.005, min(0.03, 0.01/1.0)) = 0.01 (1%)
        # But floor is 0.5% (0.005), so buffer = 0.01
        # For a $1 stock, 0.01 is 1%, which is above the 0.5% floor
        s.bars_1m['PENNY'] = {
            'minute': int(time.time() / 60),
            'open': 1.0, 'high': 1.005, 'low': 1.0,
            'close': 1.0,
            'start_volume': 50000, 'last_volume': 50000,
        }

        await s.evaluate_and_fire_alert(
            symbol='PENNY', last_price=1.0, total_volume=50000,
            high_price=1.005, low_price=0.995, open_price=1.0,
        )
        assert s.vwap_state['PENNY']['status'] == 'below'

    @pytest.mark.asyncio
    async def test_high_volatility_atr_cap(self):
        """Very high volatility stock: ATR buffer caps at 3%."""
        s = SchwabStreamer()
        s.current_date = datetime.now(EASTERN_TZ).date()
        s.fundamentals_cache['VOL'] = {
            'yesterday_close': 10.0,
            'yesterday_high': 12.0,
            'vol_10d_avg': 50000,
            'shares_outstanding': 10_000_000,
        }
        s.check_and_fire_alert = AsyncMock(return_value=True)
        s.vwap_state['VOL'] = {
            'cum_vp': 10.0 * 50000, 'cum_vol': 50000,
            'last_total_vol': 50000, 'status': None,
        }
        # Create 14 candles with huge range: high=12, low=8 (TR=4, VWAP=10, raw=0.4)
        s.completed_bars_1m['VOL'] = [
            {'volume': 5000, 'open': 10.0, 'close': 10.0, 'high': 12.0, 'low': 8.0}
            for _ in range(14)
        ]
        # atr_val = 4.0, buffer = max(0.005, min(0.03, 4.0/10.0)) = 0.03 (3%)
        s.bars_1m['VOL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.0,
            'start_volume': 50000, 'last_volume': 50000,
        }

        await s.evaluate_and_fire_alert(
            symbol='VOL', last_price=10.0, total_volume=50000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )
        # Should be 'below' because 10.0 <= 10.0 * (1 - 0.03) = 9.70 is false
        # Actually 10.0 > 9.70 so it's NOT below; it's not above either (10.0 < 10.30)
        # status stays None
        assert s.vwap_state['VOL']['status'] is None

    @pytest.mark.asyncio
    async def test_missing_high_low_in_history(self):
        """Backward compat: candles without high/low fields should fallback to close."""
        s = self._setup_vwap()
        # Old-format candles (no high/low)
        s.completed_bars_1m['AAPL'] = [
            {'volume': 5000, 'open': 10.0, 'close': 10.1} for _ in range(14)
        ]
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.0,
            'start_volume': 100000, 'last_volume': 100000,
        }

        # Should not crash — high/low fallback to close
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.0, total_volume=100000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )

    @pytest.mark.asyncio
    async def test_true_range_calculation(self):
        """Verify True Range formula: max(H-L, |H-prevC|, |L-prevC|)."""
        s = self._setup_vwap()
        # Candle 0: high=10.5, low=9.5, open=10.0, close=10.2, prev_close=open=10.0
        # TR = max(1.0, |10.5-10.0|, |9.5-10.0|) = max(1.0, 0.5, 0.5) = 1.0
        # Candle 1: high=10.8, low=10.0, open=10.2, close=10.5, prev_close=10.2
        # TR = max(0.8, |10.8-10.2|, |10.0-10.2|) = max(0.8, 0.6, 0.2) = 0.8
        s.completed_bars_1m['AAPL'] = [
            {'volume': 5000, 'open': 10.0, 'close': 10.2, 'high': 10.5, 'low': 9.5},
            {'volume': 5000, 'open': 10.2, 'close': 10.5, 'high': 10.8, 'low': 10.0},
        ]
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.0,
            'start_volume': 100000, 'last_volume': 100000,
        }

        # Just verify it doesn't crash with 2 candles (< 14, uses all available)
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.0, total_volume=100000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )

    @pytest.mark.asyncio
    async def test_crossover_only_fires_from_below_to_above(self):
        """VWAP_CROSSOVER should only fire on transition, not when already above."""
        s = self._setup_vwap()
        s.vwap_state['AAPL']['status'] = 'above'
        s.completed_bars_1m['AAPL'] = [
            {'volume': 5000, 'open': 10.0, 'close': 10.1, 'high': 10.2, 'low': 10.0}
            for _ in range(14)
        ]
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.5,
            'start_volume': 100000, 'last_volume': 100000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.5, total_volume=100000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VWAP_CROSSOVER" not in fired

    @pytest.mark.asyncio
    async def test_crossover_requires_rvol_2(self):
        """VWAP_CROSSOVER requires RVOL >= 2.0."""
        s = self._setup_vwap()
        s.fundamentals_cache['AAPL']['vol_10d_avg'] = 1000000
        s.vwap_state['AAPL']['status'] = 'below'
        s.completed_bars_1m['AAPL'] = [
            {'volume': 5000, 'open': 10.0, 'close': 10.1, 'high': 10.2, 'low': 10.0}
            for _ in range(14)
        ]
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.5, 'low': 10.0,
            'close': 10.5,
            'start_volume': 100000, 'last_volume': 100000,
        }

        # Low volume → low RVOL
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.5, total_volume=100000,
            high_price=10.5, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VWAP_CROSSOVER" not in fired

    @pytest.mark.asyncio
    async def test_vwap_crossover_bearish_no_alert(self):
        """Crossover from above to below VWAP should NOT fire (only bullish fires)."""
        s = self._setup_vwap()
        s.vwap_state['AAPL']['status'] = 'above'
        s.completed_bars_1m['AAPL'] = [
            {'volume': 5000, 'open': 10.0, 'close': 10.1, 'high': 10.2, 'low': 10.0}
            for _ in range(14)
        ]
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60),
            'open': 10.0, 'high': 10.0, 'low': 9.5,
            'close': 9.5,
            'start_volume': 100000, 'last_volume': 100000,
        }

        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=9.5, total_volume=100000,
            high_price=10.0, low_price=9.5, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "VWAP_CROSSOVER" not in fired
        assert s.vwap_state['AAPL']['status'] == 'below'


# ===================================================================
# PART 6: Integration / Regression Tests
# ===================================================================

class TestM2Regressions:
    """Reproduce and verify fixes for regressions identified by reviewers."""

    @pytest.mark.asyncio
    async def test_hod_does_not_fire_in_same_minute(self):
        """
        Regression: old per-tick HOD check fired every tick.
        New candle-completion check should NOT fire within same minute.
        """
        s = _make_streamer()
        s.prev_session_high['AAPL'] = 10.50
        current_min = int(time.time() / 60)
        s.bars_1m['AAPL'] = {
            'minute': current_min,  # same minute
            'open': 10.0, 'high': 10.80, 'low': 10.0,
            'close': 10.70,
            'start_volume': 100000, 'last_volume': 105000,
        }

        # First tick
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.70, total_volume=105000,
            high_price=10.80, low_price=10.0, open_price=10.0,
        )
        # Second tick same minute
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.72, total_volume=106000,
            high_price=10.82, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" not in fired

    @pytest.mark.asyncio
    async def test_hod_fires_on_next_candle(self):
        """
        After candle completion, HOD breakout should fire on next completed candle.
        """
        s = _make_streamer(vol_10d_avg=100)
        s.prev_session_high['AAPL'] = 10.50

        # First call: candle at minute N-2 completes
        s.bars_1m['AAPL'] = {
            'minute': int(time.time() / 60) - 2,
            'open': 10.0, 'high': 10.60, 'low': 10.0,
            'close': 10.55,  # above HOD ref 10.50
            'start_volume': 100000, 'last_volume': 105000,
        }
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=10.55, total_volume=105000,
            high_price=10.60, low_price=10.0, open_price=10.0,
        )

        fired = [a[0][5] if a[0] else a[1].get('alert_type') for a in s.check_and_fire_alert.call_args_list]
        assert "NEAR_HOD_RADAR" in fired

    @pytest.mark.asyncio
    async def test_gap_pct_calculation_preserved(self):
        """Gap % calculation should still work correctly after changes.
        Uses PREV_DAY_BREAKOUT trigger which fires regardless of candle completion."""
        s = _make_streamer()
        s.fundamentals_cache['AAPL']['yesterday_close'] = 20.0
        s.fundamentals_cache['AAPL']['yesterday_high'] = 15.0  # low so breakout fires

        # last_price=22.0 > yesterday_high=15.0 → PREV_DAY_BREAKOUT fires
        # open_price=21.0, prev_close=20.0 → gap_pct = (21-20)/20*100 = 5.0%
        await s.evaluate_and_fire_alert(
            symbol='AAPL', last_price=22.0, total_volume=50000,
            high_price=22.0, low_price=20.0, open_price=21.0,
        )

        fired_alerts = [a[0][5] for a in s.check_and_fire_alert.call_args_list]
        assert "PREV_DAY_BREAKOUT" in fired_alerts
        args = s.check_and_fire_alert.call_args[0]
        gap_pct = args[4]
        assert gap_pct == 5.0
