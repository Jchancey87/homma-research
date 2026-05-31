import sys
import os
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from config import Config

api_key = Config.FMP_API_KEY
print(f"Using API Key: {api_key[:8]}...")

ticker = 'LUNR'

endpoints = [
    # (name, path, params, version, stable)
    ("Profile (stable)", "profile", {"symbol": ticker}, 3, True),
    ("Profile (v3)", f"profile/{ticker}", {}, 3, False),
    
    ("Shares-Float (stable)", "shares-float", {"symbol": ticker}, 3, True),
    ("Shares-Float (v4)", "shares-float", {"symbol": ticker}, 4, False),
    
    ("Ratios-TTM (stable)", "ratios-ttm", {"symbol": ticker}, 3, True),
    ("Ratios-TTM (v3)", f"ratios-ttm/{ticker}", {}, 3, False),
    
    ("Income Statement (stable)", "income-statement", {"symbol": ticker, "period": "quarter", "limit": 1}, 3, True),
    ("Income Statement (v3)", f"income-statement/{ticker}", {"period": "quarter", "limit": 1}, 3, False),
    
    ("Balance Sheet (stable)", "balance-sheet-statement", {"symbol": ticker, "period": "quarter", "limit": 1}, 3, True),
    ("Balance Sheet (v3)", f"balance-sheet-statement/{ticker}", {"period": "quarter", "limit": 1}, 3, False),
    
    ("Earnings (stable)", "earnings", {"symbol": ticker}, 3, True),
    ("Earnings Calendar (v3)", "earnings-calendar", {"from": "2026-05-01", "to": "2026-06-30", "symbol": ticker}, 3, False),
    ("Earnings Historical (v3)", f"historical/earnings/{ticker}", {"limit": 4}, 3, False),
]

for name, path, params, version, stable in endpoints:
    if stable:
        url = f"https://financialmodelingprep.com/stable/{path}"
    else:
        url = f"https://financialmodelingprep.com/api/v{version}/{path}"
    
    p = {"apikey": api_key}
    p.update(params)
    
    try:
        r = requests.get(url, params=p, timeout=5)
        print(f"{name}: Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "Error Message" in data:
                print(f"  Error message in JSON: {data['Error Message']}")
            elif isinstance(data, list) and len(data) > 0:
                print(f"  Success! Found list with {len(data)} items. Keys in first item: {list(data[0].keys())}")
            elif isinstance(data, dict):
                print(f"  Success! Found dict. Keys: {list(data.keys())}")
            else:
                print(f"  Success! Empty or unexpected structure: {type(data)} - {data}")
        else:
            print(f"  Response text: {r.text[:200]}")
    except Exception as e:
        print(f"{name}: Exception: {e}")
