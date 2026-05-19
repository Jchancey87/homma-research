"""
tests/test_continuation.py
Phase 3 — async continuation picks router tests.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_list_active_returns_200(client):
    resp = await client.get("/api/continuation-picks")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_list_returns_list(client):
    resp = await client.get("/api/continuation-picks")
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_list_include_inactive(client):
    resp = await client.get("/api/continuation-picks", params={"include_inactive": "true"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_add_picks(client):
    """Batch insert two picks."""
    resp = await client.post(
        "/api/continuation-picks",
        json={
            "picks": [
                {"ticker": "TSTA", "date": "2026-01-15", "reason": "test", "rank": 1},
                {"ticker": "TSTB", "date": "2026-01-15", "reason": "test", "rank": 2},
            ]
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["inserted"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_add_idempotent(client):
    """Re-inserting same ticker+date should not raise (ON CONFLICT DO NOTHING)."""
    payload = {"picks": [{"ticker": "IDEM", "date": "2026-01-16", "rank": 1}]}
    r1 = await client.post("/api/continuation-picks", json=payload)
    r2 = await client.post("/api/continuation-picks", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_deactivate_and_delete(client):
    add = await client.post(
        "/api/continuation-picks",
        json={"picks": [{"ticker": "DDLT", "date": "2026-01-17", "rank": 1}]},
    )
    assert add.status_code == 201

    # Find the inserted pick id
    all_picks = (await client.get("/api/continuation-picks", params={"include_inactive": "true"})).json()
    pick = next((p for p in all_picks if p["ticker"] == "DDLT"), None)
    assert pick is not None
    pick_id = pick["id"]

    # Deactivate
    deact = await client.post(f"/api/continuation-picks/{pick_id}/deactivate", json={"reason": "test"})
    assert deact.status_code == 200
    assert deact.json()["success"] is True

    # Hard delete
    delete = await client.delete(f"/api/continuation-picks/{pick_id}")
    assert delete.status_code == 200
    assert delete.json()["success"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_deactivate_not_found(client):
    resp = await client.post("/api/continuation-picks/999999/deactivate", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_continuation_stats(client):
    resp = await client.get("/api/continuation-picks/stats")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
