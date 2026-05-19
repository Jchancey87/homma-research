"""
fastapi_app/chart_service_shim.py
FastAPI-compatible equivalent of services/chart_service.py.

The original chart_service uses Werkzeug FileStorage (.mimetype, .save()).
FastAPI provides UploadFile (.content_type, async .read()).  This shim
bridges the two without touching the Flask-side service.
"""
from __future__ import annotations

import os
import uuid

from fastapi import UploadFile

from .config import settings

VALID_TAGS = [
    "gap-and-hold",
    "gap-and-fade",
    "breakout-clean",
    "breakout-whipsaw",
    "multi-day-runner",
    "sector-sympathy",
    "news-fresh",
    "news-stale",
    "halt-triggered",
    "failed-follow-through",
]


def validate_tags(tags: list[str]) -> list[str]:
    """Return any tags not in the allowlist."""
    return [t for t in tags if t not in VALID_TAGS]


async def save_chart_image(
    file: UploadFile,
    ticker: str | None = None,
    capture_date: str | None = None,
    subfolder: str | None = None,
) -> str:
    """
    Validate and save an uploaded chart image.

    Returns the full filesystem path where the file was saved.
    Raises ValueError on bad MIME type or oversized file.
    """
    content_type = file.content_type or ""
    if content_type not in settings.allowed_mime_types:
        raise ValueError(
            f"Invalid file type '{content_type}'. "
            f"Allowed: {sorted(settings.allowed_mime_types)}"
        )

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise ValueError("File exceeds 10 MB limit.")

    ext = "png"
    filename_raw = file.filename or ""
    if "." in filename_raw:
        raw_ext = filename_raw.rsplit(".", 1)[-1].lower()
        if raw_ext in settings.allowed_extensions:
            ext = raw_ext

    parts = [p for p in [ticker, capture_date, str(uuid.uuid4())[:8]] if p]
    filename = "_".join(parts) + f".{ext}"

    save_dir = settings.storage_path
    if subfolder:
        save_dir = os.path.join(save_dir, subfolder)
    os.makedirs(save_dir, exist_ok=True)

    full_path = os.path.join(save_dir, filename)
    with open(full_path, "wb") as fh:
        fh.write(data)

    return full_path
