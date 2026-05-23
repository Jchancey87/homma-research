import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.mark.asyncio(loop_scope="session")
async def test_get_alerts_history(client):
    """GET /api/alerts/history must return HTTP 200 and a list of historical alerts."""
    resp = await client.get("/api/alerts/history")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)

@pytest.mark.asyncio(loop_scope="session")
async def test_get_alerts_stream_headers(client):
    """GET /api/alerts/stream must return text/event-stream content type."""
    mock_redis = MagicMock()
    mock_pubsub = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()
    mock_redis.aclose = AsyncMock()
    
    # Custom non-exhaustible mock for get_message
    calls = []
    async def mock_get_message(*args, **kwargs):
        if not calls:
            calls.append(1)
            return {'type': 'message', 'data': b'{"symbol": "TEST", "price": 10.0}'}
        await asyncio.sleep(10)  # Sleep/block to let test exit cleanly
        return None
        
    mock_pubsub.get_message = mock_get_message
    
    with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
        # Read headers to verify SSE headers
        async with client.stream("GET", "/api/alerts/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
