import requests
import json

url = "https://scanner.tradingview.com/america/scan"

# Query regular gainers with close >= 0.10 and volume >= 50,000
payload = {
    "filter": [
        {"left": "change", "operation": "greater", "right": 5},
        {"left": "volume", "operation": "greater", "right": 50000},
        {"left": "close", "operation": "greater", "right": 0.10},
        {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
    ],
    "options": {
        "active_symbols_only": True
    },
    "markets": ["america"],
    "symbols": {
        "query": {"types": []}
    },
    "sort": {
        "sortBy": "change",
        "sortOrder": "desc"
    },
    "columns": [
        "name",
        "change",
        "close",
        "volume"
    ],
    "range": [0, 50]
}

headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        rows = data.get("data", [])
        print(f"Total rows returned: {len(rows)}")
        print("\nFirst 20 returned tickers:")
        for r in rows[:20]:
            sym = r.get("d")[0]
            change = r.get("d")[1]
            close = r.get("d")[2]
            vol = r.get("d")[3]
            print(f"  {sym}: Price: {close}, Change: {change:.2f}%, Volume: {vol:,}")
    else:
        print("Error:", response.text)
except Exception as e:
    print(f"Error: {e}")
