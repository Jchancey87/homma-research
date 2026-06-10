import os
import sys
from dotenv import load_dotenv

# Find backend dir and load .env
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_env_path = os.path.join(_backend, '.env')
load_dotenv(_env_path)

if _backend not in sys.path:
    sys.path.insert(0, _backend)

from services.schwab_client import get_daily_bars
import datetime
import pytz

try:
    bars = get_daily_bars('AAPL')
    print("Fetched AAPL bars:", len(bars))
    eastern = pytz.timezone('America/New_York')
    for b in bars[-10:]:
        ts = b['t']
        dt_utc = datetime.datetime.fromtimestamp(ts / 1000.0, tz=datetime.timezone.utc)
        dt_et = dt_utc.astimezone(eastern)
        print(f"t={ts} | UTC={dt_utc.strftime('%Y-%m-%d %H:%M:%S')} | ET={dt_et.strftime('%Y-%m-%d %H:%M:%S')} | c={b['c']}")
except Exception as e:
    print("Error:", e)
