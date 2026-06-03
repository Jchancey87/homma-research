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
        
        # Mock fundamentals cache with low average volume to ensure high RVOL
        streamer.fundamentals_cache['AAPL'] = {
            'shares_outstanding': 10_000_000,
            'vol_10d_avg': 100_000,
            'low_52wk': 100.0,
        }
        
        # Mock db pool
        mock_db_pool = MagicMock()
        mock_conn = AsyncMock()
        
        # Set return value for should_fire_alert (TRUE)
        mock_conn.fetchval.return_value = True
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
        self.assertEqual(args[1], 15.0)
        self.assertEqual(args[2], timedelta(minutes=10))
        self.assertEqual(args[3], timedelta(seconds=10))
        self.assertEqual(args[4], 5)
        
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

if __name__ == '__main__':
    unittest.main()
