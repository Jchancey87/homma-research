import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from validation import EASTERN_TZ
from momentum_screener.schwab.stream_client import SchwabStreamer

@pytest.mark.asyncio
async def test_trigger_running_up():
    """RUNNING_UP fires if price rises >=3% from lowest close in last 5 candles, volume >=1.5x of 20-bar avg, not at HOD."""
    streamer = SchwabStreamer()
    streamer.current_date = datetime.now(EASTERN_TZ).date()
    streamer.fundamentals_cache['AAPL'] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': 1000,
        'shares_outstanding': 50000000,
    }
    streamer.check_and_fire_alert = AsyncMock(return_value=True)
    
    # 20 completed candles with average volume 1000, lowest close in last 5 is 100.0
    streamer.completed_bars_1m['AAPL'] = [{'volume': 1000, 'open': 100.0, 'close': 100.0} for _ in range(20)]
    streamer.bars_1m['AAPL'] = {
        'minute': int(time.time() / 60),
        'open': 101.0,
        'high': 103.5,
        'low': 101.0,
        'close': 103.5,
        'start_volume': 100000,
        'last_volume': 102000,  # 2000 candle volume (>= 1.5x avg 1000)
    }
    
    # last_price = 103.5 (>= 3% of 100.0), high_price = 104.0 (not at HOD)
    await streamer.evaluate_and_fire_alert(
        symbol='AAPL',
        last_price=103.5,
        total_volume=102000,
        high_price=104.0,
        low_price=100.0,
        open_price=101.0
    )
    
    # Check if RUNNING_UP alert was fired
    fired_alerts = [args[5] for args, kwargs in streamer.check_and_fire_alert.call_args_list]
    assert "RUNNING_UP" in fired_alerts


@pytest.mark.asyncio
async def test_trigger_bull_flag():
    """BULL_FLAG fires on breakout of 3-candle consolidation after strong move up."""
    streamer = SchwabStreamer()
    streamer.current_date = datetime.now(EASTERN_TZ).date()
    streamer.fundamentals_cache['AAPL'] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': 1000,
        'shares_outstanding': 50000000,
    }
    streamer.check_and_fire_alert = AsyncMock(return_value=True)
    
    # Setup history:
    # 5 candles strong move up (t-9 to t-5): from close 100.0 to 106.0 (6% move)
    # 3 candles consolidation (t-4 to t-2): close range 104.9 - 105.0, declining volume (1000 -> 800 -> 600)
    history = [
        {'volume': 1000, 'open': 100.0, 'close': 100.0}, # -9
        {'volume': 1000, 'open': 101.0, 'close': 102.0}, # -8
        {'volume': 1000, 'open': 102.0, 'close': 103.0}, # -7
        {'volume': 1000, 'open': 103.0, 'close': 104.5}, # -6
        {'volume': 1000, 'open': 104.5, 'close': 106.0}, # -5
        {'volume': 1000, 'open': 106.0, 'close': 105.0}, # -4 (con1)
        {'volume': 800,  'open': 105.0, 'close': 105.0}, # -3 (con2)
        {'volume': 600,  'open': 105.0, 'close': 104.9}, # -2 (con3)
        {'volume': 1000, 'open': 104.9, 'close': 104.9}, # -1
    ]
    streamer.completed_bars_1m['AAPL'] = history
    streamer.bars_1m['AAPL'] = {
        'minute': int(time.time() / 60),
        'open': 104.9,
        'high': 106.5,
        'low': 104.9,
        'close': 106.5,
        'start_volume': 100000,
        'last_volume': 102000, # 2000 volume (>= 1.5x avg)
    }
    
    # last_price = 106.5 (breaks consolidation high of 106.0)
    await streamer.evaluate_and_fire_alert(
        symbol='AAPL',
        last_price=106.5,
        total_volume=102000,
        high_price=107.0,
        low_price=104.0,
        open_price=104.9
    )
    
    fired_alerts = [args[5] for args, kwargs in streamer.check_and_fire_alert.call_args_list]
    assert "BULL_FLAG" in fired_alerts


@pytest.mark.asyncio
async def test_trigger_near_hod_radar():
    """NEAR_HOD_RADAR fires when price exceeds the previous high of day with RVOL >= 1.5."""
    streamer = SchwabStreamer()
    streamer.current_date = datetime.now(EASTERN_TZ).date()
    streamer.fundamentals_cache['AAPL'] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': 1000,  # set small so rvol calculation is large
        'shares_outstanding': 50000000,
    }
    streamer.check_and_fire_alert = AsyncMock(return_value=True)
    streamer.prev_session_high['AAPL'] = 105.0
    
    await streamer.evaluate_and_fire_alert(
        symbol='AAPL',
        last_price=105.5,
        total_volume=2000,
        high_price=105.0,
        low_price=99.0,
        open_price=100.0
    )
    
    fired_alerts = [args[5] for args, kwargs in streamer.check_and_fire_alert.call_args_list]
    assert "NEAR_HOD_RADAR" in fired_alerts


@pytest.mark.asyncio
async def test_trigger_multi_tf_confluence():
    """MULTI_TF_CONFLUENCE fires if 5-min candle is bullish >= 1% and 1-min NEAR_HOD_RADAR fired within past 60s."""
    streamer = SchwabStreamer()
    streamer.current_date = datetime.now(EASTERN_TZ).date()
    streamer.fundamentals_cache['AAPL'] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': 1000,
        'shares_outstanding': 50000000,
    }
    streamer.check_and_fire_alert = AsyncMock(return_value=True)
    
    # 5-min bullish candle: open of history[-5] = 100.0, close of history[-1] = 101.5 (1.5% move)
    streamer.completed_bars_1m['AAPL'] = [
        {'volume': 1000, 'open': 100.0, 'close': 100.2},
        {'volume': 1000, 'open': 100.2, 'close': 100.5},
        {'volume': 1000, 'open': 100.5, 'close': 100.8},
        {'volume': 1000, 'open': 100.8, 'close': 101.0},
        {'volume': 1000, 'open': 101.0, 'close': 101.5},
    ]
    
    # Record recent HOD breakout 30s ago
    streamer.last_hod_breakout_time['AAPL'] = time.time() - 30
    
    await streamer.evaluate_and_fire_alert(
        symbol='AAPL',
        last_price=101.5,
        total_volume=5000,
        high_price=102.0,
        low_price=99.0,
        open_price=100.0
    )
    
    fired_alerts = [args[5] for args, kwargs in streamer.check_and_fire_alert.call_args_list]
    assert "MULTI_TF_CONFLUENCE" in fired_alerts


@pytest.mark.asyncio
async def test_trigger_halt_resume_momentum():
    """HALT_RESUME_MOMENTUM fires 30s after resume if price is >=1% above resume price and volume >=1.5x avg."""
    streamer = SchwabStreamer()
    streamer.fundamentals_cache['AAPL'] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': 1000,
        'shares_outstanding': 50000000,
    }
    streamer.check_and_fire_alert = AsyncMock(return_value=True)
    
    streamer.completed_bars_1m['AAPL'] = [{'volume': 1000, 'open': 100.0, 'close': 100.0} for _ in range(5)]
    streamer.bars_1m['AAPL'] = {
        'minute': int(time.time() / 60),
        'open': 100.0,
        'high': 101.5,
        'low': 100.0,
        'close': 101.5,
        'start_volume': 10000,
        'last_volume': 12000,  # 2000 volume (>= 1.5x avg 1000)
    }
    streamer.last_known_price['AAPL'] = 101.5
    streamer.vwap_state['AAPL'] = {'last_total_vol': 12000}
    streamer.save_resume_to_db = AsyncMock()
    
    # Mock sleep so it doesn't actually block for 30s in test
    import momentum_screener.schwab.stream_client as sc
    print("STREAM_CLIENT FILE PATH IS:", sc.__file__)
    with patch("asyncio.sleep", AsyncMock()):
        await streamer.schedule_halt_resume_momentum_check("AAPL", 100.0)
        
    fired_alerts = [args[5] for args, kwargs in streamer.check_and_fire_alert.call_args_list]
    assert "HALT_RESUME_MOMENTUM" in fired_alerts


@pytest.mark.asyncio
async def test_tier_based_gating():
    """Verify delivery gating: Tier 3 DB only, Tier 2 DB+SSE, Tier 1 DB+SSE+Telegram."""
    streamer = SchwabStreamer()
    
    # Mock DB save
    streamer.save_alert_to_db = AsyncMock(return_value={'id': 1, 'alert_time': datetime.now()})
    
    # Mock DB pool connection and should_fire_alert return value
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 'OK'
    
    mock_db_pool = MagicMock()
    mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
    streamer.db_pool = mock_db_pool
    
    streamer.fundamentals_cache['AAPL'] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': 1000000,
        'shares_outstanding': 50000000,
    }
    
    # Mock Redis pubsub
    mock_redis = MagicMock()
    
    # Mock Celery send_task
    mock_celery = MagicMock()
    
    with patch("momentum_screener.schwab.stream_client.redis_client", mock_redis), \
         patch("momentum_screener.schwab.stream_client.celery_app", mock_celery), \
         patch("momentum_screener.schwab.stream_client.datetime") as mock_dt:
         
        mock_dt.utcnow.return_value = datetime.now()
        mock_dt.now.return_value = datetime.now(EASTERN_TZ)
        
        # Test Case 1: Tier 3 (DB only)
        streamer.watchlist_symbols = set()
        streamer.calculate_confluence_score = MagicMock(return_value=(15, "Tier 3"))
        
        mock_redis.publish.reset_mock()
        mock_celery.send_task.reset_mock()
        
        res = await streamer.check_and_fire_alert("AAPL", 10.0, 1000, 1.0, 0.0, "VOLATILITY_HALT")
        assert res is True
        assert streamer.save_alert_to_db.called
        assert not mock_redis.publish.called
        assert not mock_celery.send_task.called
        
        # Test Case 2: Tier 2 (DB + SSE/Redis only, no Telegram/Celery)
        streamer.fired_alerts_session.clear()
        streamer.calculate_confluence_score = MagicMock(return_value=(50, "Tier 2"))
        streamer.save_alert_to_db.reset_mock()
        mock_redis.publish.reset_mock()
        mock_celery.send_task.reset_mock()
        
        res = await streamer.check_and_fire_alert("AAPL", 10.0, 1000, 1.0, 0.0, "NEAR_HOD_RADAR")
        assert res is True
        assert streamer.save_alert_to_db.called
        assert mock_redis.publish.called
        assert not mock_celery.send_task.called
        
        # Test Case 3: Tier 1 (DB + SSE + Telegram)
        streamer.fired_alerts_session.clear()
        streamer.calculate_confluence_score = MagicMock(return_value=(80, "Tier 1"))
        streamer.save_alert_to_db.reset_mock()
        mock_redis.publish.reset_mock()
        mock_celery.send_task.reset_mock()
        
        res = await streamer.check_and_fire_alert("AAPL", 10.0, 1000, 1.0, 0.0, "NEAR_HOD_RADAR")
        assert res is True
        assert streamer.save_alert_to_db.called
        assert mock_redis.publish.called
        assert mock_celery.send_task.called
