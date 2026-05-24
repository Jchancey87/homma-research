import requests
import json

url = "https://scanner.tradingview.com/america/scan"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

# 1. Regular gainers
payload_reg = {
    "filter": [
        {"left": "change", "operation": "greater", "right": 5},
        {"left": "volume", "operation": "greater", "right": 50000},
        {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
    ],
    "options": {"active_symbols_only": True},
    "markets": ["america"],
    "symbols": {"query": {"types": []}},
    "sort": {"sortBy": "change", "sortOrder": "desc"},
    "columns": ["name", "change", "close", "volume", "market_cap_basic", "float_shares_outstanding", "sector"],
    "range": [0, 100]
}

# 2. Premarket gainers
payload_pre = {
    "filter": [
        {"left": "premarket_change", "operation": "greater", "right": 5},
        {"left": "premarket_volume", "operation": "greater", "right": 10000},
        {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
    ],
    "options": {"active_symbols_only": True},
    "markets": ["america"],
    "symbols": {"query": {"types": []}},
    "sort": {"sortBy": "premarket_change", "sortOrder": "desc"},
    "columns": ["name", "premarket_change", "premarket_close", "premarket_volume", "market_cap_basic", "float_shares_outstanding", "sector"],
    "range": [0, 100]
}

# 3. Postmarket gainers
payload_post = {
    "filter": [
        {"left": "postmarket_change", "operation": "greater", "right": 5},
        {"left": "postmarket_volume", "operation": "greater", "right": 10000},
        {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
    ],
    "options": {"active_symbols_only": True},
    "markets": ["america"],
    "symbols": {"query": {"types": []}},
    "sort": {"sortBy": "postmarket_change", "sortOrder": "desc"},
    "columns": ["name", "postmarket_change", "postmarket_close", "postmarket_volume", "market_cap_basic", "float_shares_outstanding", "sector"],
    "range": [0, 100]
}

candidates = {}

for label, payload in [("Regular", payload_reg), ("Pre-market", payload_pre), ("Post-market", payload_post)]:
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"{label} Status Code: {resp.status_code}")
        if resp.status_code == 200:
            rows = resp.json().get("data", [])
            print(f"  Returned {len(rows)} rows")
            for r in rows:
                d = r.get("d", [])
                sym = d[0]
                if sym and len(sym) <= 5:
                    sym = sym.upper()
                    change = d[1] or 0
                    close = d[2] or 0
                    volume = d[3] or 0
                    mcap = d[4]
                    float_sh = d[5]
                    sector = d[6]
                    
                    # Update or add if change is higher
                    if sym not in candidates or abs(change) > abs(candidates[sym]["change"]):
                        candidates[sym] = {
                            "change": change,
                            "price": close,
                            "volume": volume,
                            "market_cap": mcap,
                            "float_shares": float_sh,
                            "sector": sector
                        }
        else:
            print(f"  Failed: {resp.text}")
    except Exception as e:
        print(f"  Error: {e}")

print(f"\nTotal unique candidates: {len(candidates)}")

user_tickers = ['PCLA', 'AKTX', 'QBTX', 'ATPC', 'RGTX', 'NCPL', 'EDHL', 'AKAN', 'RYOJ', 'CODX']
found = [t for t in user_tickers if t in candidates]
print(f"Found {len(found)} of {len(user_tickers)} user tickers: {found}")
missing = [t for t in user_tickers if t not in candidates]
print(f"Missing tickers: {missing}")

print("\nDetails of user tickers found:")
for t in found:
    print(f"  {t}: {candidates[t]}")
