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


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_export(client):
    # Ensure there's at least one ticker
    await client.post(
        "/api/watchlist",
        json={"ticker": "EXPT", "sector": "Energy", "notes": "export test", "tags": ["export"]},
    )
    resp = await client.get("/api/watchlist/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "ticker,sector,notes,tags" in content
    assert "EXPT" in content
    await client.delete("/api/watchlist/EXPT")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_import(client):
    csv_content = (
        "ticker,sector,notes,tags\n"
        "IMP1,Tech,imported ticker 1,import\n"
        "IMP2,Biotech,imported ticker 2,import;biotech\n"
    )
    
    # Post CSV as a file upload
    resp = await client.post(
        "/api/watchlist/import",
        files={"file": ("test_import.csv", csv_content.encode("utf-8"), "text/csv")}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["inserted"] == 2
    
    # Retrieve and verify they exist
    list_resp = await client.get("/api/watchlist")
    tickers = [item["ticker"] for item in list_resp.json()]
    assert "IMP1" in tickers
    assert "IMP2" in tickers
    
    # Cleanup
    await client.delete("/api/watchlist/IMP1")
    await client.delete("/api/watchlist/IMP2")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_groups_crud(client):
    import uuid
    rand_suffix = uuid.uuid4().hex[:6]
    name1 = f"FDA Approved {rand_suffix}"
    name2 = f"Awaiting Trials {rand_suffix}"

    # 1. Create a watchlist group
    g1_resp = await client.post("/api/watchlist/groups", json={"name": name1})
    assert g1_resp.status_code == 201
    g1 = g1_resp.json()
    assert g1["name"] == name1
    g1_id = g1["id"]

    g2_resp = await client.post("/api/watchlist/groups", json={"name": name2})
    assert g2_resp.status_code == 201
    g2 = g2_resp.json()
    g2_id = g2["id"]

    # Try creating duplicate group name (should fail 409)
    g_dupe = await client.post("/api/watchlist/groups", json={"name": name1})
    assert g_dupe.status_code == 409

    # 2. Add ticker BIIB to FDA Approved
    r_add1 = await client.post(
        "/api/watchlist",
        json={"ticker": "BIIB", "sector": "Biotech", "notes": "Approved", "tags": ["fda"], "group_id": g1_id}
    )
    assert r_add1.status_code == 201

    # Add ticker BIIB to Awaiting Trials (different group, should succeed)
    r_add2 = await client.post(
        "/api/watchlist",
        json={"ticker": "BIIB", "sector": "Biotech", "notes": "Trials", "tags": ["trials"], "group_id": g2_id}
    )
    assert r_add2.status_code == 201

    # Add duplicate to same group (should fail 409)
    r_add_dupe = await client.post(
        "/api/watchlist",
        json={"ticker": "BIIB", "sector": "Biotech", "notes": "Approved again", "tags": ["fda"], "group_id": g1_id}
    )
    assert r_add_dupe.status_code == 409

    # 3. List watchlist for each group
    w1 = await client.get(f"/api/watchlist?group_id={g1_id}")
    assert w1.status_code == 200
    assert len(w1.json()) == 1
    assert w1.json()[0]["ticker"] == "BIIB"
    assert w1.json()[0]["notes"] == "Approved"

    w2 = await client.get(f"/api/watchlist?group_id={g2_id}")
    assert w2.status_code == 200
    assert len(w2.json()) == 1
    assert w2.json()[0]["ticker"] == "BIIB"
    assert w2.json()[0]["notes"] == "Trials"

    # List all groups
    groups_list = await client.get("/api/watchlist/groups")
    assert groups_list.status_code == 200
    group_names = [g["name"] for g in groups_list.json()]
    assert name1 in group_names
    assert name2 in group_names

    # 4. Clean up groups (this should cascade delete the items)
    del_g1 = await client.delete(f"/api/watchlist/groups/{g1_id}")
    assert del_g1.status_code == 200

    del_g2 = await client.delete(f"/api/watchlist/groups/{g2_id}")
    assert del_g2.status_code == 200

    # Verify BIIB is no longer in any group
    w1_after = await client.get(f"/api/watchlist?group_id={g1_id}")
    assert len(w1_after.json()) == 0


