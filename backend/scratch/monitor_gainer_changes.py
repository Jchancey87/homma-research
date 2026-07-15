import urllib.request
import json
import time

def main():
    prev_prices = {}
    print("Monitoring prices from /api/gainers/live for 20 seconds...")
    for i in range(10):
        try:
            r = urllib.request.urlopen("http://127.0.0.1:5000/api/gainers/live")
            data = json.loads(r.read().decode())
            gainers = data.get("gainers", [])
            
            changes = []
            for g in gainers:
                ticker = g["ticker"]
                price = g.get("last_price")
                prev = prev_prices.get(ticker)
                if prev is not None and prev != price:
                    changes.append(f"{ticker}: {prev} -> {price}")
                prev_prices[ticker] = price
            
            if changes:
                print(f"Poll {i+1:2}: {', '.join(changes)}")
            else:
                print(f"Poll {i+1:2}: No price changes")
        except Exception as e:
            print("Poll Error:", e)
        time.sleep(2)

if __name__ == "__main__":
    main()
