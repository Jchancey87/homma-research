import os
import sys

# Ensure backend directory is in sys.path so we can import modules
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from celery import Celery
from fastapi_app.config import settings

celery_app = Celery(
    "homma_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["fastapi_app.tasks.llm_tasks"]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="US/Eastern",
    enable_utc=True,
    worker_prefetch_multiplier=1, # Since these are heavy LLM/scraping tasks, don't prefetch too many
)

if __name__ == "__main__":
    celery_app.start()
