"""
tests/test_health.py
Phase 1 gate — verifies the FastAPI app boots and the /health endpoint
responds correctly, including DB connectivity.
"""
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_health_returns_200(client):
    """GET /health must return HTTP 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_health_shape(client):
    """Response body must include status, db, and version keys."""
    resp = await client.get("/health")
    body = resp.json()
    assert "status" in body
    assert "db" in body
    assert "version" in body


@pytest.mark.asyncio(loop_scope="session")
async def test_health_db_ok(client):
    """DB must be reachable (status == 'ok' and db == 'ok')."""
    resp = await client.get("/health")
    body = resp.json()
    assert body["status"] == "ok", f"Expected ok, got: {body}"
    assert body["db"] == "ok", f"DB unreachable: {body}"


@pytest.mark.asyncio(loop_scope="session")
async def test_root_returns_200(client):
    """GET / must return HTTP 200 with a message key."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()
