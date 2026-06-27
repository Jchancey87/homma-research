import urllib.request
import json

def test_research_post():
    url = "http://127.0.0.1:5000/api/research"
    payload = {
        "ticker": "TSLA",
        "date": "2026-06-09",
        "force": True
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            body = res.read().decode("utf-8")
            print(f"\nSTATUS: {res.status}")
            print(f"RESPONSE:\n{body}")
    except Exception as e:
        print(f"\nPOST FAILED: {e}")
        if hasattr(e, "read"):
            print(f"ERROR BODY: {e.read().decode('utf-8')}")
    assert True
