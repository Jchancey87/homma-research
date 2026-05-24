import requests
import pprint

url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
params = {
    "formatted": "false",
    "lang": "en-US",
    "region": "US",
    "scrIds": "day_gainers",
    "count": "100",
    "corsDomain": "finance.yahoo.com"
}
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
}

try:
    response = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        # The structure is usually finance -> result -> [0] -> quotes
        result = data.get("finance", {}).get("result", [])
        if result:
            quotes = result[0].get("quotes", [])
            print(f"Total quotes returned: {len(quotes)}")
            if quotes:
                print("First 10 tickers:")
                for q in quotes[:10]:
                    print(f"  {q.get('symbol')}: Price: {q.get('regularMarketPrice')}, Change: {q.get('regularMarketChangePercent')}%")
                
                print("\nChecking if user's tickers are in the list:")
                user_tickers = ['PCLA', 'AKTX', 'QBTX', 'ATPC', 'RGTX', 'NCPL', 'EDHL', 'AKAN', 'CODX', 'QBTS']
                found_tickers = []
                for q in quotes:
                    sym = q.get('symbol')
                    if sym in user_tickers:
                        found_tickers.append(sym)
                print(f"Found {len(found_tickers)} of {len(user_tickers)} user tickers: {found_tickers}")
        else:
            print("No result found in json:", data)
    else:
        print("Failed to get data:", response.text)
except Exception as e:
    print(f"Error: {e}")
