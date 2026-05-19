"""
tests/test_observations.py
Phase 3 — async observations router tests.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_list_returns_200(client):
    resp = await client.get("/api/observations")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_list_returns_list(client):
    resp = await client.get("/api/observations")
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_create_and_delete(client):
    create_resp = await client.post(
        "/api/observations",
        json={
            "ticker": "AAPL",
            "date": "2026-01-15",
            "body": "Looks strong — continuation candidate.",
            "title": "Morning note",
            "sentiment": "bullish",
            "tags": ["gap-up"],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    obs_id = create_resp.json()["id"]
    assert isinstance(obs_id, int)

    del_resp = await client.delete(f"/api/observations/{obs_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_update(client):
    r = await client.post(
        "/api/observations",
        json={"ticker": "NVDA", "date": "2026-01-15", "body": "initial", "sentiment": "neutral"},
    )
    obs_id = r.json()["id"]

    put = await client.put(f"/api/observations/{obs_id}", json={"body": "updated body"})
    assert put.status_code == 200
    assert put.json()["success"] is True

    await client.delete(f"/api/observations/{obs_id}")


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_update_not_found(client):
    resp = await client.put("/api/observations/999999", json={"body": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_delete_not_found(client):
    resp = await client.delete("/api/observations/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_filter_by_ticker(client):
    resp = await client.get("/api/observations", params={"ticker": "ZZZZ"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_filter_by_sentiment(client):
    resp = await client.get("/api/observations", params={"sentiment": "bearish"})
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_observations_ticker_route(client):
    resp = await client.get("/api/observations/AAPL")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
