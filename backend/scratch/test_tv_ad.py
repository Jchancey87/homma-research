import requests

def test_tv_ad():
    url = "https://scanner.tradingview.com/america/scan"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36",
        "Content-Type": "application/json"
    }
    
    # Advances payload
    payload_adv = {
        "filter": [
            {"left": "close", "operation": "in_range", "right": [2.0, 25.0]},
            {"left": "volume", "operation": "greater", "right": 0},
            {"left": "change", "operation": "greater", "right": 0},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "range": [0, 1]
    }
    
    # Declines payload
    payload_dec = {
        "filter": [
            {"left": "close", "operation": "in_range", "right": [2.0, 25.0]},
            {"left": "volume", "operation": "greater", "right": 0},
            {"left": "change", "operation": "less", "right": 0},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]}
        ],
        "options": {"active_symbols_only": True},
        "markets": ["america"],
        "symbols": {"query": {"types": []}},
        "range": [0, 1]
    }
    
    try:
        r_adv = requests.post(url, json=payload_adv, headers=headers, timeout=10)
        r_dec = requests.post(url, json=payload_dec, headers=headers, timeout=10)
        
        adv_count = r_adv.json().get("totalCount", 0)
        dec_count = r_dec.json().get("totalCount", 0)
        
        print(f"Advances: {adv_count}")
        print(f"Declines: {dec_count}")
        if dec_count > 0:
            print(f"Ratio: {adv_count / dec_count:.2f} : 1")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_tv_ad()
