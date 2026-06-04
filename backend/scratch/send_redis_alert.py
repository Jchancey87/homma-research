import sys
import os
import json
import redis
import time
from datetime import datetime

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi_app.config import settings

def send_web_ui_simulation_loop():
    print("--- Starting Web UI Alert Simulation Loop ---")
    redis_url = settings.celery_broker_url
    print("Connecting to Redis:", redis_url)
    r = redis.from_url(redis_url)
    
    mock_alerts = [
        {'symbol': 'TSLA', 'price': 220.50, 'rvol': 5.2, 'alert_type': 'VWAP_CROSSOVER'},
        {'symbol': 'AAPL', 'price': 175.40, 'rvol': 3.1, 'alert_type': 'HOD_BREAKOUT'},
        {'symbol': 'NVDA', 'price': 125.10, 'rvol': 4.6, 'alert_type': 'ATR_BREAKOUT'},
        {'symbol': 'AMD', 'price': 160.25, 'rvol': 3.9, 'alert_type': 'VOL_SPIKE'},
        {'symbol': 'MSFT', 'price': 415.80, 'rvol': 2.1, 'alert_type': 'VWAP_CROSSOVER'}
    ]
    
    channel = 'screener:alerts'
    
    for i, mock in enumerate(mock_alerts):
        alert_payload = {
            'symbol': mock['symbol'],
            'price': mock['price'],
            'volume': 5000000,
            'rvol': mock['rvol'],
            'gap_pct': 3.5,
            'float_shares': 3000000000,
            'alert_type': mock['alert_type'],
            'time': datetime.now().isoformat()
        }
        
        print(f"\n[{i+1}/5] Publishing mock alert for {mock['symbol']}...")
        subscribers = r.publish(channel, json.dumps(alert_payload))
        print(f"Delivered to {subscribers} active frontend subscribers.")
        
        if i < len(mock_alerts) - 1:
            print("Sleeping for 6 seconds before next alert...")
            time.sleep(6)
            
    print("\n--- Simulation Loop Finished ---")

if __name__ == "__main__":
    send_web_ui_simulation_loop()
