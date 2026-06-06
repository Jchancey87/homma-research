import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

# Set path correctly going up from backend/scratch/
_SCRATCH_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRATCH_DIR)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _BACKEND_DIR)

from momentum_screener.schwab.stream_client import SchwabStreamer

class TestStreamClientAlerts(unittest.IsolatedAsyncioTestCase):
    @patch('momentum_screener.schwab.stream_client.redis_client')
    @patch('momentum_screener.schwab.stream_client.celery_app')
    async def test_evaluate_and_fire_alert_triggers_correctly(self, mock_celery, mock_redis):
        # Instantiate SchwabStreamer
        streamer = SchwabStreamer()
        streamer.watchlist_symbols = {'AAPL'}
        
        # Mock fundamentals cache with low average volume to ensure high RVOL
        streamer.fundamentals_cache['AAPL'] = {
            'shares_outstanding': 10_000_000,
            'vol_10d_avg': 100_000,
            'low_52wk': 100.0,
        }
        
        # Mock db pool
        mock_db_pool = MagicMock()
        mock_conn = AsyncMock()
        
        # Set return value for should_fire_alert ('OK')
        mock_conn.fetchval.return_value = 'OK'
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        streamer.db_pool = mock_db_pool
        
        # Mock save_alert_to_db method
        streamer.save_alert_to_db = AsyncMock()
        
        # Call evaluate_and_fire_alert under HOD_BREAKOUT conditions
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=15.0,
            total_volume=2_000_000,
            high_price=14.0,
            low_price=12.0,
            open_price=13.0
        )
        
        # Verify db query to should_fire_alert was made
        mock_conn.fetchval.assert_called_once()
        query = mock_conn.fetchval.call_args[0][0]
        args = mock_conn.fetchval.call_args[0][1:]
        self.assertIn("alerts.should_fire_alert", query)
        self.assertEqual(args[0], 'AAPL')
        self.assertEqual(args[1], 'HOD_BREAKOUT')
        self.assertEqual(args[2], 15.0)
        self.assertEqual(args[3], timedelta(minutes=10))
        self.assertEqual(args[4], timedelta(seconds=10))
        self.assertEqual(args[5], 5)
        self.assertEqual(args[6], 0.02)  # Adaptive pct for $15.0
        from config import Config
        self.assertEqual(args[7], timedelta(minutes=Config.ALERT_MIN_TIME_COOLDOWN_MINS))
        self.assertEqual(args[8], 'percent')
        
        # Verify save_alert_to_db was called
        streamer.save_alert_to_db.assert_called_once_with(
            'AAPL', 15.0, 2_000_000, unittest.mock.ANY, unittest.mock.ANY,
            10_000_000, 'HOD_BREAKOUT'
        )
        
        # Verify publish to Redis
        mock_redis.publish.assert_called_once()
        channel, payload_str = mock_redis.publish.call_args[0]
        self.assertEqual(channel, 'screener:alerts')
        import json
        payload = json.loads(payload_str)
        self.assertEqual(payload['symbol'], 'AAPL')
        self.assertEqual(payload['price'], 15.0)
        self.assertEqual(payload['alert_type'], 'HOD_BREAKOUT')
        
        # Verify Celery send_task was called
        mock_celery.send_task.assert_called_once_with(
            "fastapi_app.tasks.alerts.send_telegram_alert_task",
            args=[payload]
        )
        print("Mock test passed successfully!")

    @patch('momentum_screener.schwab.stream_client.redis_client')
    @patch('momentum_screener.schwab.stream_client.celery_app')
    async def test_vwap_crossover_watchlist_filtering(self, mock_celery, mock_redis):
        # 1. Test symbol NOT in watchlist
        streamer = SchwabStreamer()
        streamer.fundamentals_cache['AAPL'] = {
            'shares_outstanding': 10_000_000,
            'vol_10d_avg': 100_000,
            'low_52wk': 100.0,
        }
        
        # Mock db pool
        mock_db_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 'OK'
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        streamer.db_pool = mock_db_pool
        streamer.save_alert_to_db = AsyncMock()
        
        # Status state: set to below so a crossover can trigger
        streamer.vwap_state['AAPL'] = {
            'cum_vp': 10.0 * 1000000,
            'cum_vol': 1000000,
            'last_total_vol': 1000000,
            'status': 'below'
        }
        streamer.watchlist_symbols = set()  # Empty watchlist
        
        # vwap will be 10.0, last_price is 15.0 (crossed above vwap * 1.02)
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=15.0,
            total_volume=2_000_000,
            high_price=16.0,
            low_price=9.0,
            open_price=9.5
        )
        
        # VWAP crossover alert should NOT fire because AAPL is not in the watchlist
        streamer.save_alert_to_db.assert_not_called()
        mock_redis.publish.assert_not_called()
        mock_celery.send_task.assert_not_called()
        
        # 2. Test symbol IN watchlist
        streamer.watchlist_symbols = {'AAPL'}
        # Reset mocks
        mock_conn.fetchval.reset_mock()
        mock_redis.publish.reset_mock()
        mock_celery.send_task.reset_mock()
        streamer.save_alert_to_db.reset_mock()
        
        # Set status back to 'below' for AAPL since evaluate_and_fire_alert would have set it to 'above'
        streamer.vwap_state['AAPL']['status'] = 'below'
        
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=15.0,
            total_volume=2_000_000,
            high_price=16.0,
            low_price=9.0,
            open_price=9.5
        )
        
        # VWAP crossover alert SHOULD fire because AAPL is in the watchlist
        streamer.save_alert_to_db.assert_called_once_with(
            'AAPL', 15.0, 2_000_000, unittest.mock.ANY, unittest.mock.ANY,
            10_000_000, 'VWAP_CROSSOVER'
        )
        mock_redis.publish.assert_called_once()
        mock_celery.send_task.assert_called_once()
        print("VWAP crossover watchlist filtering test passed successfully!")

    @patch('momentum_screener.schwab.stream_client.redis_client')
    @patch('momentum_screener.schwab.stream_client.celery_app')
    async def test_volatility_halt_resume(self, mock_celery, mock_redis):
        streamer = SchwabStreamer()
        streamer.fundamentals_cache['AAPL'] = {
            'shares_outstanding': 10_000_000,
            'vol_10d_avg': 100_000,
            'low_52wk': 100.0,
        }
        streamer.save_halt_to_db = AsyncMock()
        streamer.save_resume_to_db = AsyncMock()
        
        # Test Halt (TRADING_STATUS = 'H')
        streamer.on_level1_equity_message({
            'content': [{
                'key': 'AAPL',
                'TRADING_STATUS': 'H',
                'LAST_PRICE': 150.0,
                'TOTAL_VOLUME': 500_000
            }]
        })
        await asyncio.sleep(0.1)
        
        streamer.save_halt_to_db.assert_called_once_with('AAPL')
        mock_redis.publish.assert_called_once()
        mock_celery.send_task.assert_called_once()
        
        # Reset mocks
        mock_redis.publish.reset_mock()
        mock_celery.send_task.reset_mock()
        
        # Test Resume (TRADING_STATUS = 'ACTIVE')
        streamer.on_level1_equity_message({
            'content': [{
                'key': 'AAPL',
                'TRADING_STATUS': 'ACTIVE',
                'LAST_PRICE': 151.0,
                'TOTAL_VOLUME': 510_000
            }]
        })
        await asyncio.sleep(0.1)
        
        streamer.save_resume_to_db.assert_called_once_with('AAPL')
        mock_redis.publish.assert_called_once()
        mock_celery.send_task.assert_called_once()
        print("Volatility halt/resume test passed successfully!")

    @patch('momentum_screener.schwab.stream_client.redis_client')
    @patch('momentum_screener.schwab.stream_client.celery_app')
    async def test_volume_spike(self, mock_celery, mock_redis):
        streamer = SchwabStreamer()
        streamer.watchlist_symbols = {'AAPL'}
        streamer.fundamentals_cache['AAPL'] = {
            'shares_outstanding': 10_000_000,
            'vol_10d_avg': 100_000,
            'low_52wk': 100.0,
        }
        
        mock_db_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 'OK'
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        streamer.db_pool = mock_db_pool
        streamer.save_alert_to_db = AsyncMock()
        
        # Populate history with 20 completed bars of volume 1000
        history = streamer.completed_bars_1m.setdefault('AAPL', [])
        for _ in range(20):
            history.append({'volume': 1000, 'open': 10.0, 'close': 10.0})
            
        # Mock time to control minutes
        with patch('time.time', return_value=100000.0):
            # First tick in current minute
            await streamer.evaluate_and_fire_alert(
                symbol='AAPL',
                last_price=10.0,
                total_volume=1_000_000,
                high_price=10.5,
                low_price=9.5,
                open_price=10.0
            )
            
        # Move to next minute to trigger completion of the previous bar
        with patch('time.time', return_value=100065.0):
            # Trigger evaluation: price rose 5% (>=1%), volume delta = 10,000 (10x average)
            await streamer.evaluate_and_fire_alert(
                symbol='AAPL',
                last_price=10.5,
                total_volume=1_010_000,
                high_price=11.0,
                low_price=9.5,
                open_price=10.0
            )
            
        await asyncio.sleep(0.1)
        streamer.save_alert_to_db.assert_any_call(
            'AAPL', 10.5, 1_010_000, unittest.mock.ANY, unittest.mock.ANY,
            10_000_000, 'VOLUME_SPIKE'
        )
        print("Volume spike test passed successfully!")

    @patch('momentum_screener.schwab.stream_client.redis_client')
    @patch('momentum_screener.schwab.stream_client.celery_app')
    async def test_prev_day_breakout(self, mock_celery, mock_redis):
        streamer = SchwabStreamer()
        streamer.watchlist_symbols = {'AAPL'}
        streamer.fundamentals_cache['AAPL'] = {
            'shares_outstanding': 10_000_000,
            'vol_10d_avg': 100_000,
            'low_52wk': 10.0,
            'yesterday_high': 15.0
        }
        
        mock_db_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 'OK'
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        streamer.db_pool = mock_db_pool
        streamer.save_alert_to_db = AsyncMock()
        
        # 1. Price is below yesterday_high (HOD_BREAKOUT prevented by high_price=30.0)
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=14.5,
            total_volume=500_000,
            high_price=30.0,
            low_price=13.0,
            open_price=14.0
        )
        streamer.save_alert_to_db.assert_not_called()
        
        # 2. Price breaks above yesterday_high
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=15.5,
            total_volume=510_000,
            high_price=30.0,
            low_price=13.0,
            open_price=14.0
        )
        streamer.save_alert_to_db.assert_called_once_with(
            'AAPL', 15.5, 510_000, unittest.mock.ANY, unittest.mock.ANY,
            10_000_000, 'PREV_DAY_BREAKOUT'
        )
        
        # Reset mock
        streamer.save_alert_to_db.reset_mock()
        
        # 3. Price remains above, but alert shouldn't fire again (first time today)
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=15.7,
            total_volume=520_000,
            high_price=30.0,
            low_price=13.0,
            open_price=14.0
        )
        streamer.save_alert_to_db.assert_not_called()
        print("Previous day high breakout test passed successfully!")

    @unittest.skip("VWAP bounces disabled by user request")
    @patch('momentum_screener.schwab.stream_client.redis_client')
    @patch('momentum_screener.schwab.stream_client.celery_app')
    async def test_vwap_bounce(self, mock_celery, mock_redis):
        streamer = SchwabStreamer()
        streamer.fundamentals_cache['AAPL'] = {
            'shares_outstanding': 10_000_000,
            'vol_10d_avg': 100_000,
            'low_52wk': 10.0,
        }
        
        mock_db_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 'OK'
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
        streamer.db_pool = mock_db_pool
        streamer.save_alert_to_db = AsyncMock()
        
        # Set up VWAP = 10.0
        streamer.vwap_state['AAPL'] = {
            'cum_vp': 10.0 * 1000,
            'cum_vol': 1000,
            'last_total_vol': 1000,
            'status': 'above'
        }
        
        # declining volume history
        streamer.completed_bars_1m['AAPL'] = [
            {'volume': 300, 'open': 10.0, 'close': 10.0},
            {'volume': 200, 'open': 10.0, 'close': 10.0}
        ]
        
        # 1. Price pulls back to within 0.5% above VWAP (e.g. 10.03)
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=10.03,
            total_volume=1000,
            high_price=30.0,
            low_price=9.5,
            open_price=9.8
        )
        self.assertTrue(streamer.vwap_state['AAPL']['vwap_test'])
        self.assertEqual(streamer.vwap_state['AAPL']['vwap_low'], 10.03)
        streamer.save_alert_to_db.assert_not_called()
        
        # Change volume history to expanding
        streamer.completed_bars_1m['AAPL'] = [
            {'volume': 200, 'open': 10.0, 'close': 10.0},
            {'volume': 400, 'open': 10.0, 'close': 10.0}
        ]
        
        # 2. Price bounces by >= 1% (e.g. 10.15, which is 1.2% off 10.03)
        await streamer.evaluate_and_fire_alert(
            symbol='AAPL',
            last_price=10.15,
            total_volume=1000,
            high_price=30.0,
            low_price=9.5,
            open_price=9.8
        )
        
        streamer.save_alert_to_db.assert_called_once_with(
            'AAPL', 10.15, 1000, unittest.mock.ANY, unittest.mock.ANY,
            10_000_000, 'VWAP_BOUNCE'
        )
        self.assertFalse(streamer.vwap_state['AAPL']['vwap_test'])
        print("VWAP support bounce test passed successfully!")

if __name__ == '__main__':
    unittest.main()
