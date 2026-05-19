"""
tests/test_charts.py
Phase 3 — async charts router tests.
"""
from __future__ import annotations

import io
import json
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_list_returns_200(client):
    resp = await client.get("/api/charts")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_list_returns_list(client):
    resp = await client.get("/api/charts")
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_get_not_found(client):
    resp = await client.get("/api/charts/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_filter_by_ticker(client):
    resp = await client.get("/api/charts", params={"ticker": "ZZZZ"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_upload_and_crud(client):
    """Upload → get → update → gemini-import → delete lifecycle."""
    # Upload a tiny 1×1 PNG (valid PNG magic bytes)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload_resp = await client.post(
        "/api/charts",
        files={"image": ("test.png", io.BytesIO(png_bytes), "image/png")},
        data={
            "ticker": "AAPL",
            "capture_date": "2026-01-15",
            "timeframe": "5m",
            "setup_type": "breakout",
            "cleanliness_score": "7",
            "notes": "Test note",
            "tags": json.dumps(["gap-and-hold"]),
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    body = upload_resp.json()
    assert "id" in body
    chart_id = body["id"]

    # GET by id
    get_resp = await client.get(f"/api/charts/{chart_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["ticker"] == "AAPL"

    # PUT update
    put_resp = await client.put(
        f"/api/charts/{chart_id}",
        json={"notes": "Updated note", "cleanliness_score": 9},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["success"] is True

    # Gemini import (JSON variant)
    gi_resp = await client.post(
        f"/api/charts/{chart_id}/gemini-import-json",
        json={"analysis_text": "Looks bullish"},
    )
    assert gi_resp.status_code == 200
    assert gi_resp.json()["success"] is True

    # DELETE
    del_resp = await client.delete(f"/api/charts/{chart_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Confirm gone
    gone = await client.get(f"/api/charts/{chart_id}")
    assert gone.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_upload_invalid_tag(client):
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
    resp = await client.post(
        "/api/charts",
        files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
        data={
            "ticker": "TSLA",
            "capture_date": "2026-01-15",
            "tags": json.dumps(["not-a-valid-tag"]),
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_put_no_fields_rejected(client):
    resp = await client.put("/api/charts/999999", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_delete_not_found(client):
    resp = await client.delete("/api/charts/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_charts_gemini_import_not_found(client):
    resp = await client.post("/api/charts/999999/gemini-import-json", json={"analysis_text": "x"})
    assert resp.status_code == 404
