import requests
import json

url = "https://scanner.tradingview.com/america/scan"

# Query top gainers: change > 5%, volume > 50k, stock types
payload = {
    "filter": [
        {"left": "change", "operation": "greater", "right": 5},
        {"left": "volume", "operation": "greater", "right": 50000},
        {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
    ],
    "options": {
        "active_symbols_only": True
    },
    "markets": ["america"],
    "symbols": {
        "query": {"types": []},
        "sortBy": "change",
        "sortOrder": "desc"
    },
    "columns": [
        "name",
        "change",
        "close",
        "volume",
        "market_cap_basic"
    ],
    "range": [0, 100]
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        rows = data.get("data", [])
        print(f"Total tickers returned from TradingView: {len(rows)}")
        
        user_tickers = ['PCLA', 'AKTX', 'QBTX', 'ATPC', 'RGTX', 'NCPL', 'EDHL', 'AKAN', 'CODX', 'QBTS']
        found_tickers = {}
        
        print("\nTop 15 TradingView Gainers:")
        for idx, row in enumerate(rows[:15]):
            sym = row.get("d", [None])[0]
            change = row.get("d", [None])[1]
            close = row.get("d", [None])[2]
            vol = row.get("d", [None])[3]
            print(f"  {sym}: Price: {close}, Change: {change:.2f}%, Volume: {vol}")
            
        for row in rows:
            sym = row.get("d", [None])[0]
            change = row.get("d", [None])[1]
            close = row.get("d", [None])[2]
            vol = row.get("d", [None])[3]
            if sym in user_tickers:
                found_tickers[sym] = {"price": close, "change": change, "volume": vol}
                
        print(f"\nChecking if user's tickers are in the list:")
        print(f"Found {len(found_tickers)} of {len(user_tickers)} user tickers:")
        for sym, details in found_tickers.items():
            print(f"  {sym}: Price: {details['price']}, Change: {details['change']:.2f}%, Volume: {details['volume']}")
    else:
        print("Failed to fetch:", response.text)
except Exception as e:
    print(f"Error: {e}")
