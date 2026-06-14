"""
fastapi_app/config.py — Re-export of the unified settings module.

Historically this file duplicated env-var reads with a divergent DATABASE_URL
default (different password + host from backend/config.py). RFC-003 unified
it with backend/config.py to eliminate the silent configuration bug.

The symbol ``settings`` is now identical to ``from config import settings``,
so no caller code needs to change.
"""
from config import settings  # noqa: F401
