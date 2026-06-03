"""
backend/scratch/test_telegram_alert.py

Scratch verification script to test format, execution, and error handling of send_telegram_alert_task.
"""
import sys
import os
from unittest.mock import patch, MagicMock
import httpx

# Add backend directory to sys.path so we can import fastapi_app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi_app.tasks.alerts import send_telegram_alert_task
from fastapi_app.config import settings

def run_tests():
    print("=== Running send_telegram_alert_task tests ===")

    # Test case 1: Task skipped when settings not configured
    print("\nTest 1: Verification when settings are NOT configured")
    with patch.object(settings, 'telegram_bot_token', ''), \
         patch.object(settings, 'telegram_chat_id', ''):
        alert_payload = {
            'symbol': 'AAPL',
            'price': 150.25,
            'volume': 1200000,
            'rvol': 3.45,
            'gap_pct': 4.20,
            'float_shares': 15000000000,
            'alert_type': 'VOL_SPIKE',
            'time': '2026-06-03T03:52:00.123456'
        }
        res = send_telegram_alert_task(alert_payload)
        print("Result:", res)
        assert res['status'] == 'skipped'
        assert res['reason'] == 'not_configured'
        print("SUCCESS: Skipped correctly.")

    # Test case 2: Task successfully posts to Telegram Bot API when configured (using mocked network call)
    print("\nTest 2: Verification of payload formatting and post request (Mocked HTTP call)")
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}
    mock_response.raise_for_status = MagicMock()

    with patch.object(settings, 'telegram_bot_token', 'mock_bot_token'), \
         patch.object(settings, 'telegram_chat_id', 'mock_chat_id'), \
         patch('httpx.post', return_value=mock_response) as mock_post:

        alert_payload = {
            'symbol': 'TSLA',
            'price': 220.50,
            'volume': 5000000,
            'rvol': 5.2,
            'gap_pct': 8.5,
            'float_shares': 3100000000,
            'alert_type': 'HIGH_VOLUME_UP_BREAKOUT',
            'time': '2026-06-03T10:30:15.987654'
        }

        res = send_telegram_alert_task(alert_payload)
        print("Result:", res)
        
        # Verify httpx.post was called with the correct URL and json payload
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.telegram.org/botmock_bot_token/sendMessage"
        
        json_payload = kwargs['json']
        assert json_payload['chat_id'] == 'mock_chat_id'
        assert json_payload['parse_mode'] == 'Markdown'
        
        text = json_payload['text']
        print("Generated Message Format:\n-------------------------")
        print(text)
        print("-------------------------")
        
        # Assert format matches expected Markdown formatting
        assert "🚨 *BREAKOUT DETECTED* 🚨" in text
        assert "- *Ticker:* $TSLA" in text
        assert "- *Price:* $220.50" in text
        assert "- *Signal:* HIGH\\_VOLUME\\_UP\\_BREAKOUT" in text  # Underscores escaped
        assert "- *Volume ratio:* 5.2x" in text
        assert "- *Time:* 2026-06-03 10:30:15" in text # Formatted cleanly
        
        assert res['status'] == 'success'
        assert res['response'] == {"ok": True, "result": {"message_id": 999}}
        print("SUCCESS: Mocked dispatch and formatting verified successfully.")

    # Test case 3: HTTP status error handling
    print("\nTest 3: Verification of error handling on HTTP failure")
    mock_error_response = MagicMock(spec=httpx.Response)
    mock_error_response.status_code = 400
    mock_error_response.text = "Bad Request: chat not found"
    
    # Mocking standard HTTPStatusError behavior
    dummy_request = httpx.Request("POST", "https://api.telegram.org/botmock_bot_token/sendMessage")
    mock_error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Client error",
        request=dummy_request,
        response=mock_error_response
    )

    with patch.object(settings, 'telegram_bot_token', 'mock_bot_token'), \
         patch.object(settings, 'telegram_chat_id', 'mock_chat_id'), \
         patch('httpx.post', return_value=mock_error_response):
        
        try:
            send_telegram_alert_task(alert_payload)
            print("ERROR: Expected exception, but task completed successfully")
            assert False
        except httpx.HTTPStatusError as e:
            print("SUCCESS: Caught expected HTTPStatusError:", str(e))

if __name__ == "__main__":
    run_tests()
