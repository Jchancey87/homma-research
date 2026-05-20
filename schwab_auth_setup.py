import os
import sys

# Add repo root to sys.path
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
# Add backend to sys.path
_BACKEND_DIR = os.path.join(_REPO_ROOT, 'backend')
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND_DIR, '.env'))

from momentum_screener.schwab.auth import setup_oauth

if __name__ == '__main__':
    setup_oauth()
