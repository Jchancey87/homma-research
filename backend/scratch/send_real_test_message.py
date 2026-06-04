import sys
import os

# Add backend directory to sys.path so we can import fastapi_app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi_app.tasks.alerts import send_telegram_alert_task
from fastapi_app.config import settings

def send_real_test():
    print("--- Executing Live Telegram Bot Test ---")
    print("Telegram Token loaded:", settings.telegram_bot_token[:8] + "..." if settings.telegram_bot_token else "NONE")
    print("Telegram Chat ID loaded:", settings.telegram_chat_id)
    
    alert_payload = {
        'symbol': 'TSLA',
        'price': 220.50,
        'volume': 5000000,
        'rvol': 5.2,
        'gap_pct': 8.5,
        'float_shares': 3100000000,
        'alert_type': 'VWAP_CROSSOVER',
        'time': '2026-06-03T10:30:15.987654'
    }
    
    try:
        res = send_telegram_alert_task(alert_payload)
        print("\nSUCCESS: Alert task finished.")
        print("Response:", res)
    except Exception as e:
        print("\nFAILURE: Failed to dispatch real alert.")
        print("Error details:", str(e))

if __name__ == "__main__":
    send_real_test()
