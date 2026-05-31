import os
import sys
from dotenv import load_dotenv

# Set path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, 'backend'))

load_dotenv(os.path.join(_REPO_ROOT, 'backend', '.env'))

from momentum_screener.schwab.auth import get_client

def test_api():
    try:
        client = get_client()
        print("Successfully created client from token file.")
        
        # Test 1: Market Data API
        print("Testing Market Data API (get_quote)...")
        r = client.get_quote('AAPL')
        print(f"Market Data Response Status Code: {r.status_code}")
        if r.status_code == 200:
            print("Market Data API works! Sample quote data:")
            print(r.json().get('AAPL', {}).get('quote', {}))
        else:
            print(f"Market Data API failed: {r.text}")
            
        # Test 2: Trader/Preferences API
        print("\nTesting Trader API (get_user_preferences)...")
        r_pref = client.get_user_preferences()
        print(f"Trader API Response Status Code: {r_pref.status_code}")
        if r_pref.status_code == 200:
            print("Trader API works! User preferences successfully retrieved.")
        else:
            print(f"Trader API failed: {r_pref.text}")
            
    except Exception as e:
        print(f"Error during API test: {e}")

if __name__ == '__main__':
    test_api()
