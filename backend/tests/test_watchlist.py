"""
tests/test_watchlist.py
Phase 3 — async watchlist router tests.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_list_returns_200(client):
    resp = await client.get("/api/watchlist")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_list_returns_list(client):
    resp = await client.get("/api/watchlist")
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_add_and_delete(client):
    """Add a ticker (no enrichment needed since sector+notes+tags supplied) then delete."""
    add_resp = await client.post(
        "/api/watchlist",
        json={"ticker": "TSTT", "sector": "Tech", "notes": "Test ticker", "tags": ["test"]},
    )
    assert add_resp.status_code == 201, add_resp.text
    assert add_resp.json()["ticker"] == "TSTT"

    del_resp = await client.delete("/api/watchlist/TSTT")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_duplicate_returns_409(client):
    """Adding the same ticker twice should return 409."""
    payload = {"ticker": "DUPE", "sector": "Energy", "notes": "dup test", "tags": ["test"]}
    r1 = await client.post("/api/watchlist", json=payload)
    assert r1.status_code == 201

    r2 = await client.post("/api/watchlist", json=payload)
    assert r2.status_code == 409

    # Cleanup
    await client.delete("/api/watchlist/DUPE")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_update(client):
    await client.post(
        "/api/watchlist",
        json={"ticker": "UPDT", "sector": "Health", "notes": "before", "tags": ["test"]},
    )
    put_resp = await client.put("/api/watchlist/UPDT", json={"notes": "after"})
    assert put_resp.status_code == 200
    assert put_resp.json()["success"] is True

    await client.delete("/api/watchlist/UPDT")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_update_not_found(client):
    resp = await client.put("/api/watchlist/ZZZZ", json={"notes": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_delete_not_found(client):
    resp = await client.delete("/api/watchlist/NOPE")
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_mark_viewed(client):
    await client.post(
        "/api/watchlist",
        json={"ticker": "VWED", "sector": "Tech", "notes": "view test", "tags": ["test"]},
    )
    resp = await client.post("/api/watchlist/VWED/viewed")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    await client.delete("/api/watchlist/VWED")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_prices_returns_dict(client):
    """Prices endpoint should return {} or a dict of ticker→price data."""
    resp = await client.get("/api/watchlist/prices")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
