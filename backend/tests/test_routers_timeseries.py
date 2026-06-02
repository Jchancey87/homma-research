"""
tests/test_routers_timeseries.py
Integration tests for the strategies, signals, indicators, and OHLCV API routes.
"""
from __future__ import annotations

import pytest
from datetime import date, datetime, timedelta, timezone

from fastapi_app.db import get_pool
from fastapi_app.db.ohlcv import insert_bars_daily, insert_bars_1min
from fastapi_app.db.indicators import insert_indicators


@pytest.mark.asyncio(loop_scope="session")
async def test_strategies_lifecycle_and_backtests(client):
    # Proactive cleanup of potential residual data
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM strategies WHERE name = $1", "TEST_ROUTE_EMA_CROSS")

    # 1. Create a strategy
    payload = {
        "name": "TEST_ROUTE_EMA_CROSS",
        "description": "EMA crossover strategy for route testing",
        "version": "1.2.3",
        "asset_class": "equity",
        "timeframes": ["1D", "1h"],
        "parameters": {"fast": 9, "slow": 21},
        "is_active": True
    }
    resp = await client.post("/api/strategies", json=payload)
    assert resp.status_code == 201
    strat = resp.json()
    assert strat["id"] is not None
    assert strat["name"] == "TEST_ROUTE_EMA_CROSS"
    strat_id = strat["id"]

    # Test duplicate name restriction
    resp = await client.post("/api/strategies", json=payload)
    assert resp.status_code == 409

    # 2. Get the strategy
    resp = await client.get(f"/api/strategies/{strat_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "TEST_ROUTE_EMA_CROSS"

    # 3. List strategies
    resp = await client.get("/api/strategies")
    assert resp.status_code == 200
    strats = resp.json()
    assert len(strats) >= 1
    assert any(s["id"] == strat_id for s in strats)

    # List active only
    resp = await client.get("/api/strategies", params={"active_only": True})
    assert resp.status_code == 200
    assert any(s["id"] == strat_id for s in resp.json())

    # 4. Update the strategy
    update_payload = {
        "description": "Updated EMA description",
        "is_active": False
    }
    resp = await client.put(f"/api/strategies/{strat_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated EMA description"
    assert resp.json()["is_active"] is False

    # 5. Save backtest run
    bt_payload = {
        "symbol": "AAPL",
        "timeframe": "1D",
        "start_date": "2026-01-01",
        "end_date": "2026-05-01",
        "parameters": {"fast": 9, "slow": 21},
        "metrics": {
            "total_trades": 12,
            "win_rate": 0.5833,
            "profit_factor": 1.45,
            "net_pnl": 1200.50,
            "max_drawdown": 0.085,
            "sharpe_ratio": 1.25,
            "sortino_ratio": 1.62,
            "avg_win": 350.0,
            "avg_loss": -210.0
        },
        "trades": [{"type": "buy", "price": 172.5}, {"type": "sell", "price": 178.2}],
        "equity_curve": [10000.0, 10350.0, 10140.0, 11200.5],
        "notes": "Fast backtest for testing purposes"
    }
    resp = await client.post(f"/api/strategies/{strat_id}/backtests", json=bt_payload)
    assert resp.status_code == 201
    bt_id = resp.json()["id"]
    assert bt_id is not None

    # 6. List strategy backtests
    resp = await client.get(f"/api/strategies/{strat_id}/backtests")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) >= 1
    assert runs[0]["id"] == bt_id
    assert runs[0]["strategy_name"] == "TEST_ROUTE_EMA_CROSS"

    # Get detailed backtest run
    resp = await client.get(f"/api/strategies/backtests/{bt_id}")
    assert resp.status_code == 200
    run_detail = resp.json()
    assert run_detail["win_rate"] == 0.5833

    # 7. Delete the strategy and check cascades
    resp = await client.delete(f"/api/strategies/{strat_id}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    # Verify strategy is gone
    resp = await client.get(f"/api/strategies/{strat_id}")
    assert resp.status_code == 404

    # Verify backtest run cascades to deletion
    resp = await client.get(f"/api/strategies/backtests/{bt_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio(loop_scope="session")
async def test_signals_routing(client):
    # Proactive cleanup of potential residual data
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM strategies WHERE name = $1", "TEST_ROUTE_SIGNAL_STRAT")

    # 1. Create a strategy to link to
    strat_payload = {
        "name": "TEST_ROUTE_SIGNAL_STRAT",
        "is_active": True
    }
    resp = await client.post("/api/strategies", json=strat_payload)
    assert resp.status_code == 201
    strat_id = resp.json()["id"]

    # 2. POST signal to webhooks
    sig_payload = {
        "symbol": "TSLA",
        "signal_type": "ENTRY_LONG",
        "price": 178.50,
        "strategy_id": strat_id,
        "timeframe": "15m",
        "stop_loss": 172.00,
        "take_profit": 195.00,
        "confidence": 0.85,
        "metadata": {"reason": "RSI oversold + double bottom"}
    }
    resp = await client.post("/api/webhook/signal", json=sig_payload)
    assert resp.status_code == 201
    sig_id = resp.json()["id"]
    assert sig_id is not None

    # 3. GET signals for symbol
    resp = await client.get("/api/signals/TSLA")
    assert resp.status_code == 200
    signals = resp.json()
    assert len(signals) >= 1
    assert signals[0]["id"] == sig_id
    assert signals[0]["strategy_name"] == "TEST_ROUTE_SIGNAL_STRAT"
    assert signals[0]["metadata"]["reason"] == "RSI oversold + double bottom"

    # Clean up strategy (cascades to signal deletion via SET NULL or CASCADE depending on schema, we used SET NULL)
    await client.delete(f"/api/strategies/{strat_id}")


@pytest.mark.asyncio(loop_scope="session")
async def test_ohlcv_and_indicators_queries(client):
    pool = get_pool()
    
    # 1. Insert dummy OHLCV & indicators directly to DB so we have predictable test data
    today_dt = datetime.now(timezone.utc)
    bars_1min = [
        ("MSFT", today_dt, 420.0, 422.0, 419.0, 421.5, 50000),
    ]
    bars_daily = [
        ("MSFT", today_dt.date(), 418.0, 423.0, 417.5, 422.0, 2000000),
    ]
    indicators = [
        (today_dt, "MSFT", "1min", "EMA_20", 420.5, None, None),
        (today_dt, "MSFT", "1min", "RSI_14", 55.4, None, None),
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            await insert_bars_1min(conn, bars_1min)
            await insert_bars_daily(conn, bars_daily)
            await insert_indicators(conn, indicators)

    # 2. Fetch daily OHLCV
    resp = await client.get("/api/ohlcv/MSFT", params={"timeframe": "daily"})
    assert resp.status_code == 200
    daily_bars = resp.json()
    assert len(daily_bars) >= 1
    assert daily_bars[-1]["close"] == 422.0

    # 3. Fetch 1min OHLCV
    resp = await client.get("/api/ohlcv/MSFT", params={"timeframe": "1min"})
    assert resp.status_code == 200
    min_bars = resp.json()
    assert len(min_bars) >= 1
    assert min_bars[-1]["close"] == 421.5

    # 4. Fetch resample OHLCV
    resp = await client.get("/api/ohlcv/MSFT/resample", params={
        "bucket": "5 minutes",
        "start": (today_dt - timedelta(days=1)).isoformat(),
        "end": (today_dt + timedelta(days=1)).isoformat()
    })
    assert resp.status_code == 200
    resampled_bars = resp.json()
    assert len(resampled_bars) >= 1

    # 5. Fetch single indicator
    resp = await client.get("/api/indicators/MSFT", params={"indicator_name": "EMA_20"})
    assert resp.status_code == 200
    ind_vals = resp.json()
    assert len(ind_vals) >= 1
    assert ind_vals[0]["value"] == 420.5

    # 6. Fetch multi indicators
    resp = await client.get("/api/indicators/MSFT", params={"indicator_names": ["EMA_20", "RSI_14"]})
    assert resp.status_code == 200
    ind_vals_multi = resp.json()
    assert len(ind_vals_multi) >= 2
    names = [i["indicator_name"] for i in ind_vals_multi]
    assert "EMA_20" in names
    assert "RSI_14" in names
    
    # 7. Clean up dummy test data to keep hypertable tidy
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM price_history_1min WHERE symbol = 'MSFT'")
        await conn.execute("DELETE FROM price_history_daily WHERE symbol = 'MSFT'")
        await conn.execute("DELETE FROM indicators WHERE symbol = 'MSFT'")


@pytest.mark.asyncio(loop_scope="session")
async def test_global_signals_endpoint(client):
    pool = get_pool()
    # Cleanup potential leftover strategies
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM strategies WHERE name = $1", "TEST_GLOBAL_SIG_STRAT")

    # 1. Create a strategy to link to
    strat_payload = {
        "name": "TEST_GLOBAL_SIG_STRAT",
        "is_active": True
    }
    resp = await client.post("/api/strategies", json=strat_payload)
    assert resp.status_code == 201
    strat_id = resp.json()["id"]

    # 2. Insert signals for different symbols
    sig1_payload = {
        "symbol": "AAPL",
        "signal_type": "ENTRY_SHORT",
        "price": 180.20,
        "strategy_id": strat_id,
        "timeframe": "5m"
    }
    sig2_payload = {
        "symbol": "NVDA",
        "signal_type": "ENTRY_LONG",
        "price": 950.00,
        "strategy_id": strat_id,
        "timeframe": "1m"
    }
    await client.post("/api/webhook/signal", json=sig1_payload)
    await client.post("/api/webhook/signal", json=sig2_payload)

    # 3. GET signals globally
    resp = await client.get("/api/signals")
    assert resp.status_code == 200
    signals = resp.json()
    assert len(signals) >= 2
    
    # 4. Check details of global list
    symbols = [s["symbol"] for s in signals]
    assert "AAPL" in symbols
    assert "NVDA" in symbols
    
    # 5. Clean up strategy (signals cascade delete or set null)
    await client.delete(f"/api/strategies/{strat_id}")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM signals WHERE symbol IN ('AAPL', 'NVDA')")


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_data_from_timescaledb(client):
    pool = get_pool()
    # 1. Insert dummy 1-minute OHLCV data for test ticker on a specific date (need >= 55 bars for indicators)
    test_dt = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    bars = [
        ("TESTCHAR", test_dt + timedelta(minutes=i), 100.0 + i, 105.0 + i, 99.0 + i, 103.0 + i, 50000)
        for i in range(60)
    ]
    async with pool.acquire() as conn:
        async with conn.transaction():
            await insert_bars_1min(conn, bars)

    # 2. Fetch chart data for TESTCHAR on that date
    resp = await client.get("/api/research/chart-data", params={
        "ticker": "TESTCHAR",
        "date": "2026-06-01"
    })
    assert resp.status_code == 200
    res = resp.json()
    assert "ohlcv" in res
    assert len(res["ohlcv"]) >= 2
    assert res["ohlcv"][0]["open"] >= 100.0
    assert res["ohlcv"][-1]["close"] > res["ohlcv"][0]["open"]
    
    # 3. Clean up
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM price_history_1min WHERE symbol = 'TESTCHAR'")
