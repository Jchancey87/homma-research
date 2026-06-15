"""
tests/test_chart_service.py
Unit tests for services/chart_service.py (RFC-004 QW-2).

Pure tests — no Flask FileStorage, no FastAPI UploadFile, no HTTP layer.
The end-to-end multipart upload path is covered by
tests/test_charts.py::test_charts_upload_and_crud.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.chart_service import (  # noqa: E402
    VALID_TAGS,
    _resolve_extension,
    save_chart_image,
    validate_tags,
)


# ── validate_tags ─────────────────────────────────────────────────────────────

def test_validate_tags_returns_empty_for_all_valid():
    assert validate_tags(["gap-and-hold", "breakout-clean"]) == []


def test_validate_tags_returns_invalid_substrings():
    invalid = validate_tags(["gap-and-hold", "not-a-real-tag", "breakout-clean"])
    assert invalid == ["not-a-real-tag"]


def test_validate_tags_empty_input():
    assert validate_tags([]) == []


def test_valid_tags_constant_contains_expected_entries():
    expected = {
        "gap-and-hold", "gap-and-fade",
        "breakout-clean", "breakout-whipsaw",
        "multi-day-runner", "sector-sympathy",
        "news-fresh", "news-stale",
        "halt-triggered", "failed-follow-through",
    }
    assert set(VALID_TAGS) == expected


# ── _resolve_extension (private helper) ────────────────────────────────────────

def test_resolve_extension_default_png_when_no_dot():
    assert _resolve_extension("screenshot") == "png"


def test_resolve_extension_default_png_when_empty():
    assert _resolve_extension("") == "png"


def test_resolve_extension_uses_whitelisted_ext():
    assert _resolve_extension("chart.png") == "png"
    assert _resolve_extension("chart.jpg") == "jpg"
    assert _resolve_extension("chart.jpeg") == "jpeg"
    assert _resolve_extension("chart.webp") == "webp"


def test_resolve_extension_rejects_non_whitelisted():
    assert _resolve_extension("malicious.exe") == "png"
    assert _resolve_extension("payload.php") == "png"
    assert _resolve_extension("archive.tar.gz") == "png"  # 'gz' not allowed, falls back


def test_resolve_extension_case_insensitive():
    assert _resolve_extension("chart.PNG") == "png"
    assert _resolve_extension("chart.JPG") == "jpg"


# ── save_chart_image — uses tmp_path fixture for filesystem isolation ────────

def test_save_chart_image_writes_to_storage_path(tmp_path, monkeypatch):
    """Happy path: writes blob to STORAGE_PATH with a unique filename."""
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))

    path = save_chart_image(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
        "image/png",
        "AAPL_2026-06-14.png",
        ticker="AAPL",
        capture_date="2026-06-14",
    )

    assert path.startswith(str(tmp_path))
    assert path.endswith(".png")
    assert os.path.exists(path)
    assert os.path.basename(path).startswith("AAPL_2026-06-14_")
    # uuid8 suffix is appended
    assert len(os.path.basename(path).split("_")) >= 3


def test_save_chart_image_writes_correct_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))
    payload = b"unique-magic-bytes-12345"

    path = save_chart_image(payload, "image/png", "x.png")

    with open(path, "rb") as fh:
        assert fh.read() == payload


def test_save_chart_image_creates_subfolder(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))

    path = save_chart_image(
        b"x", "image/png", "x.png",
        subfolder="annotated",
    )
    assert os.path.dirname(path) == os.path.join(str(tmp_path), "annotated")
    assert os.path.exists(path)


def test_save_chart_image_works_without_metadata(tmp_path, monkeypatch):
    """ticker/capture_date optional — uuid8 still guarantees uniqueness."""
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))

    path = save_chart_image(b"x", "image/png", "x.png")
    assert os.path.exists(path)
    # Filename should be just the uuid suffix + ext
    basename = os.path.basename(path)
    assert basename.endswith(".png")
    assert len(basename) == len("xxxxxxxx.png")  # 8 hex chars + .png


def test_save_chart_image_unique_filenames(tmp_path, monkeypatch):
    """Two saves with identical metadata should produce different files."""
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))

    p1 = save_chart_image(b"a", "image/png", "x.png", ticker="AAPL", capture_date="2026-06-14")
    p2 = save_chart_image(b"b", "image/png", "x.png", ticker="AAPL", capture_date="2026-06-14")
    assert p1 != p2
    assert os.path.exists(p1) and os.path.exists(p2)


def test_save_chart_image_rejects_bad_mime(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))
    with pytest.raises(ValueError, match="Invalid file type"):
        save_chart_image(b"x", "application/x-msdownload", "evil.exe")


def test_save_chart_image_rejects_oversized_blob(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))
    # MAX_UPLOAD_BYTES is 10 MB; pass 10 MB + 1 byte
    big_blob = b"\x00" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="exceeds 10 MB limit"):
        save_chart_image(big_blob, "image/png", "big.png")


def test_save_chart_image_accepts_exact_limit(tmp_path, monkeypatch):
    """Boundary: blob == MAX_UPLOAD_BYTES is allowed; > is rejected."""
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))
    at_limit = b"\x00" * (10 * 1024 * 1024)
    path = save_chart_image(at_limit, "image/png", "x.png")
    assert os.path.exists(path)


def test_save_chart_image_extension_from_filename_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setattr("config.Config.STORAGE_PATH", str(tmp_path))
    path = save_chart_image(b"x", "image/jpeg", "screenshot.jpg")
    assert path.endswith(".jpg")
