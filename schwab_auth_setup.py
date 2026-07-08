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
    
    print("\n🔄 Attempting to restart PM2 services...")
    import subprocess
    try:
        # Try to restart the fastapi-backend and schwab-streamer PM2 services
        res = subprocess.run(["pm2", "restart", "fastapi-backend", "schwab-streamer"], capture_output=True, text=True)
        if res.returncode == 0:
            print("✅ PM2 services (fastapi-backend, schwab-streamer) restarted successfully.")
        else:
            # If PM2 is running under root, this might fail, which is expected before migration.
            print("⚠️ PM2 restart command returned non-zero. If services run as root, run: sudo pm2 restart all")
            print(res.stderr)
    except FileNotFoundError:
        print("⚠️ 'pm2' command not found in PATH. Please restart your services manually.")
    except Exception as e:
        print(f"⚠️ Failed to restart PM2 services: {e}")

