"""
tests/test_gainers.py
Phase 2 — async gainers router tests.
"""
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_returns_200(client):
    resp = await client.get("/api/gainers")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_returns_list(client):
    resp = await client.get("/api/gainers")
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_filter_min_gap(client):
    resp = await client.get("/api/gainers", params={"min_gap": 10})
    assert resp.status_code == 200
    data = resp.json()
    for row in data:
        assert row.get("gap_pct") is None or row["gap_pct"] >= 10


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_summary_shape(client):
    resp = await client.get("/api/gainers/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert "total" in body
    assert "gainers" in body
    assert isinstance(body["gainers"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_sectors_returns_list(client):
    resp = await client.get("/api/gainers/sectors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_ticker_history_returns_200(client):
    resp = await client.get("/api/gainers/ticker-history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_ticker_history_sort_param(client):
    resp = await client.get("/api/gainers/ticker-history", params={"sort": "appearances", "limit": 5})
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_float_buckets_shape(client):
    resp = await client.get("/api/gainers/float-buckets")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert "buckets" in body
    assert isinstance(body["buckets"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_sector_rotation_returns_list(client):
    resp = await client.get("/api/gainers/sector-rotation")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_export_returns_csv_content_type(client):
    resp = await client.get("/api/gainers/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
