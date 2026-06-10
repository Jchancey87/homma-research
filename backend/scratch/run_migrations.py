import os
import sys
from dotenv import load_dotenv

# Find backend dir and load .env
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_env_path = os.path.join(_backend, '.env')
load_dotenv(_env_path)

if _backend not in sys.path:
    sys.path.insert(0, _backend)

from database import init_db
try:
    print("Running database migrations...")
    init_db()
    print("Database migrations applied successfully!")
except Exception as e:
    print("Failed to run migrations:", e)
