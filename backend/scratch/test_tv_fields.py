import requests
import json

url = "https://scanner.tradingview.com/america/scan"

# Query regular gainers with float and market cap fields included
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
        "volume",
        "market_cap_basic",
        "float_shares_outstanding",
        "sector"
    ],
    "range": [0, 50]
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
        print(f"Total rows returned: {len(rows)}")
        print("\nTop 20 tickers with float & sector:")
        for r in rows[:20]:
            d = r.get("d", [])
            sym = d[0]
            change = d[1]
            close = d[2]
            vol = d[3]
            mcap = d[4]
            float_sh = d[5]
            sector = d[6]
            
            float_str = f"{float_sh / 1e6:.2f}M" if float_sh else "N/A"
            mcap_str = f"{mcap / 1e6:.2f}M" if mcap else "N/A"
            
            print(f"  {sym}: Price: {close}, Change: {change:.2f}%, Volume: {vol:,}, Float: {float_str}, MCap: {mcap_str}, Sector: {sector}")
    else:
        print("Error:", response.text)
except Exception as e:
    print(f"Error: {e}")
