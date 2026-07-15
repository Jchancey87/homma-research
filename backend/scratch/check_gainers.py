import urllib.request
import json

def main():
    r = urllib.request.urlopen("http://127.0.0.1:5000/api/gainers/live")
    data = json.loads(r.read().decode())
    print("Redis Connected:", data.get("redis_connected"))
    print("Fast Mode Active:", data.get("fast_mode_active"))
    print("Streaming Symbols Count:", data.get("streaming_symbols_count"))
    print("\nGAINERS:")
    for g in data.get("gainers", []):
        ticker = g.get("ticker")
        last_price = g.get("last_price")
        close_price = g.get("close_price")
        net_pct = g.get("net_percent_change")
        gap_pct = g.get("gap_pct")
        quote_time = g.get("quote_time")
        updated_at = g.get("updated_at")
        print(f"Ticker: {ticker:6} | Price: {last_price or close_price} | Net%: {net_pct or gap_pct} | Time: {quote_time or updated_at}")

if __name__ == "__main__":
    main()
