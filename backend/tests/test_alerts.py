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
    
    # Custom mock for get_message that raises CancelledError to stop the generator
    calls = []
    async def mock_get_message(*args, **kwargs):
        if not calls:
            calls.append(1)
            return {'type': 'message', 'data': b'{"symbol": "TEST", "price": 10.0}'}
        raise asyncio.CancelledError()
        
    mock_pubsub.get_message = mock_get_message
    
    with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
        # Read headers to verify SSE headers
        async with client.stream("GET", "/api/alerts/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio(loop_scope="session")
async def test_get_alert_dates(client):
    """GET /api/alerts/dates must return HTTP 200 and a list of dates."""
    resp = await client.get("/api/alerts/dates")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_alerts_daily_summary(client):
    """GET /api/alerts/daily-summary must return HTTP 200 and a daily gainer alerts summary dictionary."""
    resp = await client.get("/api/alerts/daily-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert "tickers" in body
    assert isinstance(body["tickers"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_save_alert_feedback(client):
    """POST /api/alerts/{id}/feedback must successfully update the feedback score and notes in the DB."""
    from fastapi_app.db import get_pool
    from datetime import datetime, timezone
    
    mock_time = datetime.now(timezone.utc)
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO public.screener_alerts (symbol, alert_time, trigger_price, alert_type)
            VALUES ('TEST', $1, 10.5, 'TEST_ALERT')
            RETURNING id
        """, mock_time)
        alert_id = row['id']
        
    try:
        feedback_data = {
            "alert_time": mock_time.isoformat(),
            "feedback_score": "helpful",
            "feedback_notes": "Perfect breakout timing!"
        }
        
        post_resp = await client.post(f"/api/alerts/{alert_id}/feedback", json=feedback_data)
        assert post_resp.status_code == 200
        assert post_resp.json()["status"] == "success"
        
        async with pool.acquire() as conn:
            updated_row = await conn.fetchrow("""
                SELECT feedback_score, feedback_notes
                FROM public.screener_alerts
                WHERE id = $1 AND alert_time = $2
            """, alert_id, mock_time)
            
            assert updated_row is not None
            assert updated_row["feedback_score"] == "helpful"
            assert updated_row["feedback_notes"] == "Perfect breakout timing!"
            
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM public.screener_alerts WHERE id = $1 AND alert_time = $2", alert_id, mock_time)

