import time
import requests

ENDPOINTS = [
    ("/api/continuation-picks", "http://127.0.0.1:5000/api/continuation-picks"),
    ("/api/market/breadth", "http://127.0.0.1:5000/api/market/breadth"),
    ("/api/market/momentum-breadth", "http://127.0.0.1:5000/api/market/momentum-breadth"),
    ("/api/gainers/live", "http://127.0.0.1:5000/api/gainers/live"),
    ("/api/gainers/repeat-runners", "http://127.0.0.1:5000/api/gainers/repeat-runners"),
    ("/api/gainers/float-buckets", "http://127.0.0.1:5000/api/gainers/float-buckets"),
    ("/api/gainers/follow-through", "http://127.0.0.1:5000/api/gainers/follow-through"),
    ("/api/gainers/sector-rotation", "http://127.0.0.1:5000/api/gainers/sector-rotation"),
    ("/api/watchlist", "http://127.0.0.1:5000/api/watchlist"),
    ("/api/watchlist/prices", "http://127.0.0.1:5000/api/watchlist/prices"),
    ("/api/observations?limit=5", "http://127.0.0.1:5000/api/observations?limit=5"),
    ("/api/market/calendar", "http://127.0.0.1:5000/api/market/calendar")
]

def profile():
    print(f"{'Endpoint':<40} | {'Status':<6} | {'Time (ms)':<10} | {'Response Size (bytes)':<22}")
    print("-" * 88)
    for name, url in ENDPOINTS:
        try:
            start = time.perf_counter()
            r = requests.get(url)
            end = time.perf_counter()
            elapsed_ms = (end - start) * 1000
            print(f"{name:<40} | {r.status_code:<6} | {elapsed_ms:>9.2f} | {len(r.content):>21}")
        except Exception as e:
            print(f"{name:<40} | ERROR  | {'-':>9} | {str(e)[:30]}")

if __name__ == "__main__":
    profile()
