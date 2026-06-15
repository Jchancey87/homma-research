"""
services/chart_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Framework-agnostic chart image persistence.

Single public surface (one function, one validator, one constant):

    VALID_TAGS                       allowlist of valid chart tag strings
    validate_tags(tags) -> list      return tags NOT in the allowlist
    save_chart_image(blob,           write bytes to disk with a unique name
                      content_type,
                      filename, *,
                      ticker=None,
                      capture_date=None,
                      subfolder=None) -> str

No Flask FileStorage, no FastAPI UploadFile. Callers adapt their upload
type to (bytes, content_type, filename) and call this directly. Sync
function (blocking disk I/O); routers that need non-blocking behavior
should wrap calls in `asyncio.to_thread()`.

Originally extracted as RFC-004 QW-2 (handoff #014). Replaces the
near-duplicate [services/chart_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_service.py) (Flask-style, now dead code)
and [fastapi_app/chart_service_shim.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/chart_service_shim.py) (FastAPI-style, deleted).
"""
from __future__ import annotations

import os
import uuid
from typing import List, Optional

from config import Config

VALID_TAGS: List[str] = [
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


def validate_tags(tags: list) -> list:
    """Return any tags not in the allowlist (empty list = all valid)."""
    return [t for t in tags if t not in VALID_TAGS]


def _resolve_extension(filename: str) -> str:
    """Extract a whitelisted extension from the filename; default to 'png'."""
    ext = "png"
    if filename and "." in filename:
        raw_ext = filename.rsplit(".", 1)[-1].lower()
        if raw_ext in Config.ALLOWED_EXTENSIONS:
            ext = raw_ext
    return ext


def save_chart_image(
    blob: bytes,
    content_type: str,
    filename: str,
    *,
    ticker: Optional[str] = None,
    capture_date: Optional[str] = None,
    subfolder: Optional[str] = None,
) -> str:
    """Validate and persist an uploaded chart image. Returns the full path.

    Args:
        blob: Raw image bytes (already read from the upload stream).
        content_type: MIME type from the upload (e.g. "image/png").
        filename: Original filename (used for extension resolution only).
        ticker: Optional ticker symbol — embedded in the saved filename.
        capture_date: Optional YYYY-MM-DD date — embedded in the filename.
        subfolder: Optional subdirectory under Config.STORAGE_PATH.

    Returns:
        Absolute filesystem path of the saved file.

    Raises:
        ValueError: On bad MIME type or oversized blob.
    """
    if content_type not in Config.ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Invalid file type '{content_type}'. "
            f"Allowed: {sorted(Config.ALLOWED_MIME_TYPES)}"
        )

    if len(blob) > Config.MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds 10 MB limit.")

    ext = _resolve_extension(filename)

    parts = [p for p in [ticker, capture_date, str(uuid.uuid4())[:8]] if p]
    final_filename = "_".join(parts) + f".{ext}"

    save_dir = Config.STORAGE_PATH
    if subfolder:
        save_dir = os.path.join(save_dir, subfolder)
    os.makedirs(save_dir, exist_ok=True)

    full_path = os.path.join(save_dir, final_filename)
    with open(full_path, "wb") as fh:
        fh.write(blob)

    return full_path
