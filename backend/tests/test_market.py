"""
tests/test_market.py
Phase 2 — async market router tests.
"""
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_breadth_returns_200(client):
    resp = await client.get("/api/market/breadth")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_breadth_shape(client):
    resp = await client.get("/api/market/breadth")
    body = resp.json()
    assert "indices" in body
    assert "bias" in body
    assert "fetched_at" in body
    assert "cache_ttl_s" in body


@pytest.mark.asyncio(loop_scope="session")
async def test_breadth_bias_is_valid(client):
    resp = await client.get("/api/market/breadth")
    body = resp.json()
    assert body["bias"] in ("risk_on", "risk_off", "neutral", "unknown")


@pytest.mark.asyncio(loop_scope="session")
async def test_calendar_returns_200(client):
    resp = await client.get("/api/market/calendar")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_calendar_shape(client):
    resp = await client.get("/api/market/calendar")
    body = resp.json()
    assert "events" in body
    assert "source" in body
    assert isinstance(body["events"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_calendar_event_fields(client):
    """If events exist, they must have required fields."""
    resp = await client.get("/api/market/calendar")
    body = resp.json()
    for event in body["events"]:
        assert "date" in event
        assert "event" in event
        assert "impact" in event
        assert event["impact"] in ("high", "medium")
