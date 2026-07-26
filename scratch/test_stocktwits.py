import requests
import json

def test_symbol_detail_and_trending(symbol):
    print(f"\n--- Testing Symbol Details & Trending info for {symbol} ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    # 1. Symbol Stream
    url_stream = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    r = requests.get(url_stream, headers=headers, timeout=10)
    if r.status_code == 200:
        data = r.json()
        sym_info = data.get("symbol", {})
        msgs = data.get("messages", [])
        print(f"Symbol: {sym_info.get('symbol')} | Title: {sym_info.get('title')}")
        print(f"Watchers (Watchlist Count): {sym_info.get('watchlist_count')}")
        
        # Calculate sentiment score & message frequency metrics
        bullish = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}) and m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
        bearish = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}) and m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
        total_labeled = bullish + bearish
        bull_pct = (bullish / total_labeled * 100) if total_labeled > 0 else 0
        
        print(f"Recent Messages Count: {len(msgs)}")
        print(f"Labeled Sentiment: Bullish={bullish}, Bearish={bearish} -> Bull Ratio={bull_pct:.1f}%")
        
        # Inspect top liked or recent messages
        top_msgs = sorted(msgs, key=lambda m: m.get("likes", {}).get("total", 0), reverse=True)
        print("\nTop Liked Posts:")
        for m in top_msgs[:3]:
            user = m.get("user", {}).get("username")
            followers = m.get("user", {}).get("followers")
            likes = m.get("likes", {}).get("total")
            sent = m.get("entities", {}).get("sentiment", {}).get("basic") if m.get("entities", {}).get("sentiment") else "Neutral"
            print(f"  • @{user} ({followers} followers | {likes} likes | {sent}): {m.get('body')[:120]}...")
    else:
        print(f"Stream error {r.status_code}: {r.text[:200]}")

    # 2. Trending Reason
    url_trend = f"https://api.stocktwits.com/api/2/symbols/trending/{symbol}.json"
    r2 = requests.get(url_trend, headers=headers, timeout=10)
    if r2.status_code == 200:
        t_data = r2.json()
        summary = t_data.get("symbol", {}).get("trends", {}).get("summary")
        print(f"Trending Reason: {summary}")
    else:
        print(f"Trending Info Response: {r2.status_code}")

if __name__ == "__main__":
    # Test on a small cap gainer (UAMY was in trending) and TSLA
    test_symbol_detail_and_trending("UAMY")
    test_symbol_detail_and_trending("OSS")
