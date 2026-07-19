"""
backend/tests/e2e/conftest.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
E2E-specific pytest fixtures.

Extends the parent conftest.py (session pool, HTTPX client, mock_external_apis)
with:
  - Database seeding helpers for stock_fundamentals, screener_alerts, price_history_1min
  - Redis pub/sub capture (fakeredis)
  - Celery task dispatch interceptor
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import pytest_asyncio
import asyncpg

# ---------------------------------------------------------------------------
# Path bootstrap (same as parent conftest)
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_pool():
    """Get the asyncpg pool from the db module (created by parent conftest pool_lifecycle)."""
    from fastapi_app.db import get_pool
    return get_pool()


# ---------------------------------------------------------------------------
# Fakeredis fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def fake_redis():
    """In-memory Redis substitute for pub/sub capture."""
    try:
        import fakeredis.aioredis
        server = fakeredis.aioredis.FakeServer()
        r = await fakeredis.aioredis.create_redis(server=server)
        yield r
        r.close()
        await r.wait_closed()
    except ImportError:
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(return_value=0)
        mock_redis.pubsub = MagicMock()
        yield mock_redis


# ---------------------------------------------------------------------------
# Database seeding fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def seed_alert(pool_lifecycle):
    """Factory fixture: insert a single alert into screener_alerts and return its id+time."""
    pool = _get_pool()

    async def _seed(
        symbol: str = "AAPL",
        alert_type: str = "NEAR_HOD_RADAR",
        trigger_price: float = 150.0,
        trigger_volume: int = 100000,
        rel_vol: float = 2.5,
        gap_pct: float = 5.0,
        float_shares: int = 50_000_000,
        alert_time: datetime | None = None,
        priority_score: int = 75,
        priority_tier: str = "Tier 1",
        vwap_dist_pct: float = 1.5,
        hod_dist_pct: float = 0.5,
        catalyst: str = "Technical / No News",
        stop_price: float = 148.0,
        stop_risk_pct: float = 1.3,
        suppressed_reason: str | None = None,
    ) -> tuple[int, datetime]:
        if alert_time is None:
            alert_time = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO screener_alerts
                    (symbol, alert_time, trigger_price, trigger_volume,
                     rel_vol, gap_pct, float_shares, alert_type,
                     priority_score, priority_tier, vwap_dist_pct,
                     hod_dist_pct, catalyst, stop_price, stop_risk_pct,
                     suppressed_reason)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                RETURNING id, alert_time
            """, symbol, alert_time, trigger_price, trigger_volume,
                rel_vol, gap_pct, float_shares, alert_type,
                priority_score, priority_tier, vwap_dist_pct,
                hod_dist_pct, catalyst, stop_price, stop_risk_pct,
                suppressed_reason)
            return row["id"], row["alert_time"]
    return _seed


@pytest_asyncio.fixture
async def seed_price_candles(pool_lifecycle):
    """Factory fixture: insert 1-min candles after an alert_time for forward return calc."""
    pool = _get_pool()

    async def _seed(
        symbol: str = "AAPL",
        alert_time: datetime | None = None,
        trigger_price: float = 150.0,
        num_candles: int = 16,
        trend: str = "up",  # "up", "down", "flat"
    ) -> list[dict]:
        if alert_time is None:
            alert_time = datetime.now(timezone.utc)

        candles = []
        price = trigger_price
        for i in range(num_candles):
            if trend == "up":
                price = trigger_price * (1 + 0.003 * (i + 1))
            elif trend == "down":
                price = trigger_price * (1 - 0.002 * (i + 1))
            else:
                price = trigger_price * (1 + 0.0005 * ((-1) ** i))

            ts = alert_time + timedelta(minutes=i + 1)
            high = price * 1.002
            low = price * 0.998
            candles.append({
                "symbol": symbol,
                "timestamp": ts,
                "open": round(trigger_price if i == 0 else candles[-1]["close"], 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(price, 2),
                "volume": 10000 + i * 2000,
            })

        async with pool.acquire() as conn:
            for c in candles:
                await conn.execute("""
                    INSERT INTO price_history_1min
                        (symbol, timestamp, open, high, low, close, volume)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    ON CONFLICT (symbol, timestamp) DO NOTHING
                """, c["symbol"], c["timestamp"], c["open"],
                    c["high"], c["low"], c["close"], c["volume"])
        return candles
    return _seed


# ---------------------------------------------------------------------------
# Celery task capture fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def capture_celery_tasks():
    """Capture Celery task dispatches via mock."""
    dispatched = []

    def mock_send_task(task_name, args=None, kwargs=None, **other):
        dispatched.append({
            "task": task_name,
            "args": args or [],
            "kwargs": kwargs or {},
            **other,
        })

    with patch("fastapi_app.celery_app.celery_app.send_task", side_effect=mock_send_task), \
         patch("momentum_screener.schwab.stream_client.celery_app.send_task", side_effect=mock_send_task):
        yield dispatched


# ---------------------------------------------------------------------------
# Redis pub/sub capture fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def capture_redis_publish(fake_redis):
    """Capture messages published to Redis channels."""
    published = []

    class PubSubCapture:
        def __init__(self, redis_client, log_list):
            self._redis = redis_client
            self._log = log_list

        async def publish(self, channel: str, message: str):
            self._log.append({"channel": channel, "message": message})
            return await self._redis.publish(channel, message)

    return PubSubCapture(fake_redis, published)


# ---------------------------------------------------------------------------
# Telegram API capture fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def capture_telegram_api():
    """Patch httpx.post to capture Telegram API calls."""
    calls = []

    def mock_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"ok": True}
        resp.raise_for_status = MagicMock()
        return resp

    with patch("fastapi_app.tasks.alerts.httpx.post", side_effect=mock_post), \
         patch("fastapi_app.tasks.alerts.send_telegram_message", return_value=True):
        yield calls


# ---------------------------------------------------------------------------
# Cleanup fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def cleanup_test_data():
    """Delete test-specific rows after each test.

    Skips cleanup when the DB pool is not available.
    """
    yield
    try:
        pool = _get_pool()
    except Exception:
        return
    async with pool.acquire() as conn:
        test_symbols = ("AAPL", "TSLA", "SNDL")
        for sym in test_symbols:
            await conn.execute("DELETE FROM price_history_1min WHERE symbol = $1", sym)
            await conn.execute("DELETE FROM screener_alerts WHERE symbol = $1", sym)
            await conn.execute("DELETE FROM screener_alerts_archive WHERE symbol = $1", sym)
