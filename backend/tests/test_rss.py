"""
tests/test_rss.py
~~~~~~~~~~~~~~~~~
Phase 4 — RSS feed router and curation tests.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_rss_sources_list(client):
    resp = await client.get("/api/rss/sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_rss_sources_crud(client):
    # 1. Create a source
    add_resp = await client.post(
        "/api/rss/sources",
        json={
            "name": "Test Feed Source",
            "feed_url": "https://example.com/test-rss-feed.xml",
            "category": "biotech",
            "is_active": True
        }
    )
    assert add_resp.status_code == 201, add_resp.text
    source_id = add_resp.json()["id"]
    assert source_id > 0

    # 2. Duplicate create should return 409
    dupe_resp = await client.post(
        "/api/rss/sources",
        json={
            "name": "Duplicate Test Feed",
            "feed_url": "https://example.com/test-rss-feed.xml",
            "category": "biotech",
            "is_active": True
        }
    )
    assert dupe_resp.status_code == 409

    # 3. Update the source
    update_resp = await client.put(
        f"/api/rss/sources/{source_id}",
        json={"name": "Updated Test Feed", "is_active": False}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["message"] == "Source updated successfully."

    # Verify updates in list
    list_resp = await client.get("/api/rss/sources")
    items = list_resp.json()
    match = [x for x in items if x["id"] == source_id]
    assert len(match) == 1
    assert match[0]["name"] == "Updated Test Feed"
    assert match[0]["is_active"] is False

    # 4. Delete the source
    del_resp = await client.delete(f"/api/rss/sources/{source_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Source deleted successfully."


@pytest.mark.asyncio(loop_scope="session")
async def test_rss_pool_empty_by_default(client):
    resp = await client.get("/api/rss/pool")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_rss_trigger_ingest(client):
    # Adding a mock source that will fail/do nothing but verify execution
    add_resp = await client.post(
        "/api/rss/sources",
        json={
            "name": "Mock Ingest Feed",
            "feed_url": "https://invalid.url.xyz/feed",
            "category": "tech",
            "is_active": True
        }
    )
    assert add_resp.status_code == 201
    source_id = add_resp.json()["id"]

    ingest_resp = await client.post("/api/rss/pool/trigger-ingest")
    assert ingest_resp.status_code == 200
    assert "stats" in ingest_resp.json()

    # Clean up
    await client.delete(f"/api/rss/sources/{source_id}")


@pytest.mark.asyncio(loop_scope="session")
async def test_rss_feed_xml_endpoint(client):
    resp = await client.get("/api/rss/feed")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/rss+xml"
    assert "<?xml" in resp.text
    assert "<rss" in resp.text
