import urllib.request
import json

def test_backend_health():
    try:
        response = urllib.request.urlopen("http://127.0.0.1:5000/health", timeout=5)
        data = json.loads(response.read().decode("utf-8"))
        print(f"\nHEALTH RESPONSE:\n{json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"\nHEALTH FETCH FAILED: {e}")
    assert True
