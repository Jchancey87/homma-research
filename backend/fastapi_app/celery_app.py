import os
import sys

# Ensure backend directory and repo root are in sys.path so we can import modules
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from celery import Celery
from fastapi_app.config import settings
from validation import EASTERN_TZ

celery_app = Celery(
    "homma_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "fastapi_app.tasks.llm_tasks",
        "fastapi_app.tasks.alerts"
    ]
)

from celery.schedules import crontab

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=EASTERN_TZ,
    enable_utc=True,
    worker_prefetch_multiplier=1, # Since these are heavy LLM/scraping tasks, don't prefetch too many
    beat_schedule={
        "enrich-watchlist-nightly": {
            "task": "tasks.enrich_watchlist_task",
            "schedule": crontab(hour=1, minute=0),  # 1:00 AM Eastern Time
        }
    }
)

if __name__ == "__main__":
    celery_app.start()
