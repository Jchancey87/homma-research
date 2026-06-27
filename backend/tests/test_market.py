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


@pytest.mark.asyncio(loop_scope="session")
async def test_momentum_breadth_returns_200(client):
    resp = await client.get("/api/market/momentum-breadth")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_momentum_breadth_shape(client):
    resp = await client.get("/api/market/momentum-breadth")
    body = resp.json()
    assert "small_cap_ad" in body
    assert "top5_avg_rvol" in body
    assert "dominant_float_theme" in body
    assert "active_halts" in body
    
    ad = body["small_cap_ad"]
    assert "advancing" in ad
    assert "declining" in ad
    assert "ratio_str" in ad
    assert "is_bullish" in ad

    rvol = body["top5_avg_rvol"]
    assert "avg_rvol" in rvol
    assert "status" in rvol
    assert "is_high" in rvol

    theme = body["dominant_float_theme"]
    assert "theme" in theme
    assert "counts" in theme

    halts = body["active_halts"]
    assert "count" in halts
    assert "tickers" in halts


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_overview_returns_200(client):
    resp = await client.get("/api/market/dashboard-overview")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_dashboard_overview_shape(client):
    resp = await client.get("/api/market/dashboard-overview")
    body = resp.json()
    assert "live_gainers" in body
    assert "watchlist" in body
    assert "watchlist_prices" in body
    assert "gainers_summary" in body
    assert "breadth" in body
    assert "calendar" in body
    assert "momentum" in body
    assert "other" in body

    # Check types
    assert isinstance(body["watchlist"], list)
    assert isinstance(body["watchlist_prices"], dict)

    # Check other shape
    other = body["other"]
    assert "repeat_runners" in other
    assert "float_buckets" in other
    assert "follow_through" in other
    assert "sector_rotation" in other
    assert "continuation_picks" in other
    assert "recent_observations" in other
    assert isinstance(other["repeat_runners"], list)
    assert isinstance(other["float_buckets"], dict)
    assert isinstance(other["follow_through"], dict)
    assert isinstance(other["sector_rotation"], list)
    assert isinstance(other["continuation_picks"], list)
    assert isinstance(other["recent_observations"], list)
