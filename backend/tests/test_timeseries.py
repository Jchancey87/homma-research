"""
tests/test_timeseries.py
Smoke tests for the new TimescaleDB data layer modules.

Tests actual DB round-trips: insert → query → verify.
Uses the session-scoped pool from conftest.py and wraps each test in a
savepoint that rolls back to avoid side effects.
"""
from __future__ import annotations

import pytest
from datetime import datetime, date, timezone, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_conn():
    """Acquire a connection from the shared session-scoped pool."""
    from fastapi_app.db import get_pool
    return get_pool()


async def _clean_test_data(pool):
    """Best-effort cleanup of test data created during this module."""
    async with pool.acquire() as conn:
        # Clean up in FK-safe order
        await conn.execute("DELETE FROM signals WHERE symbol = 'TEST' OR symbol = 'AAPL'")
        await conn.execute("DELETE FROM backtest_runs WHERE symbol = 'SPY' AND notes = 'Test backtest run'")
        await conn.execute("DELETE FROM strategies WHERE name LIKE '%_test_%' OR name LIKE '%_strat%'")
        await conn.execute("DELETE FROM indicators WHERE symbol = 'TEST'")
        await conn.execute("DELETE FROM price_history_daily WHERE symbol = 'TEST'")
        await conn.execute("DELETE FROM price_history_1min WHERE symbol = 'TEST'")


# ═══════════════════════════════════════════════════════════════════════════
# Strategies
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_strategy_create_and_get():
    from fastapi_app.db.strategies import create_strategy, get_strategy
    pool = await _get_conn()

    async with pool.acquire() as conn:
        result = await create_strategy(
            conn,
            name="test_ema_cross_01",
            description="EMA crossover test",
            version="1.0.0",
            asset_class="equity",
            timeframes=["1m", "5m"],
            parameters={"fast": 8, "slow": 21},
            is_active=True,
        )
        assert result["name"] == "test_ema_cross_01"
        assert result["is_active"] is True
        sid = result["id"]

    async with pool.acquire() as conn:
        fetched = await get_strategy(conn, sid)
        assert fetched is not None
        assert fetched["name"] == "test_ema_cross_01"

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM strategies WHERE id = $1", sid)


@pytest.mark.asyncio(loop_scope="session")
async def test_strategy_list_active():
    from fastapi_app.db.strategies import create_strategy, list_strategies
    pool = await _get_conn()

    async with pool.acquire() as conn:
        s1 = await create_strategy(conn, name="test_active_strat_02", is_active=True)
        s2 = await create_strategy(conn, name="test_inactive_strat_02", is_active=False)

    async with pool.acquire() as conn:
        active = await list_strategies(conn, active_only=True)
        names = [s["name"] for s in active]
        assert "test_active_strat_02" in names
        assert "test_inactive_strat_02" not in names

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM strategies WHERE id = ANY($1)", [s1["id"], s2["id"]])


@pytest.mark.asyncio(loop_scope="session")
async def test_strategy_update():
    from fastapi_app.db.strategies import create_strategy, update_strategy
    pool = await _get_conn()

    async with pool.acquire() as conn:
        s = await create_strategy(conn, name="test_updatable_strat_03")

    async with pool.acquire() as conn:
        updated = await update_strategy(conn, s["id"], description="Updated desc", is_active=True)
        assert updated["description"] == "Updated desc"
        assert updated["is_active"] is True

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM strategies WHERE id = $1", s["id"])


@pytest.mark.asyncio(loop_scope="session")
async def test_strategy_delete_cascades():
    from fastapi_app.db.strategies import create_strategy, delete_strategy, get_strategy
    from fastapi_app.db.strategies import save_backtest, get_backtests
    pool = await _get_conn()

    async with pool.acquire() as conn:
        s = await create_strategy(conn, name="test_deletable_strat_04")
        await save_backtest(
            conn,
            strategy_id=s["id"],
            symbol="SPY",
            timeframe="1D",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            parameters={"fast": 8},
            metrics={"total_trades": 10, "win_rate": 0.6},
        )

    async with pool.acquire() as conn:
        assert await delete_strategy(conn, s["id"]) is True
        assert await get_strategy(conn, s["id"]) is None
        backtests = await get_backtests(conn, strategy_id=s["id"])
        assert len(backtests) == 0


# ═══════════════════════════════════════════════════════════════════════════
# OHLCV
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_ohlcv_insert_and_query_daily():
    from fastapi_app.db.ohlcv import insert_bars_daily, get_bars_daily
    pool = await _get_conn()

    records = [
        ("TEST", date(2024, 6, 1), 100.0, 105.0, 99.0, 103.0, 1000000),
        ("TEST", date(2024, 6, 2), 103.0, 107.0, 102.0, 106.0, 1200000),
        ("TEST", date(2024, 6, 3), 106.0, 110.0, 105.0, 108.0, 900000),
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await insert_bars_daily(conn, records)
    assert count == 3

    async with pool.acquire() as conn:
        bars = await get_bars_daily(conn, "TEST", date(2024, 6, 1), date(2024, 6, 3))
        assert len(bars) == 3
        assert bars[0]["open"] == 100.0
        assert bars[2]["close"] == 108.0

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM price_history_daily WHERE symbol = 'TEST'")


@pytest.mark.asyncio(loop_scope="session")
async def test_ohlcv_insert_and_query_1min():
    from fastapi_app.db.ohlcv import insert_bars_1min, get_bars_1min
    pool = await _get_conn()

    base = datetime(2024, 6, 1, 14, 30, tzinfo=timezone.utc)
    records = [
        ("TEST", base + timedelta(minutes=i), 100.0+i, 101.0+i, 99.0+i, 100.5+i, 50000)
        for i in range(5)
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await insert_bars_1min(conn, records)
    assert count == 5

    async with pool.acquire() as conn:
        bars = await get_bars_1min(conn, "TEST", base, base + timedelta(minutes=4))
        assert len(bars) == 5

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM price_history_1min WHERE symbol = 'TEST'")


@pytest.mark.asyncio(loop_scope="session")
async def test_ohlcv_dedup_on_conflict():
    from fastapi_app.db.ohlcv import insert_bars_daily
    pool = await _get_conn()

    records = [("TEST", date(2024, 7, 1), 100.0, 105.0, 99.0, 103.0, 1000000)]

    async with pool.acquire() as conn:
        async with conn.transaction():
            await insert_bars_daily(conn, records)

    # Insert same data again — should skip
    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await insert_bars_daily(conn, records)
    assert count == 0

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM price_history_daily WHERE symbol = 'TEST'")


@pytest.mark.asyncio(loop_scope="session")
async def test_ohlcv_resample_1min():
    from fastapi_app.db.ohlcv import insert_bars_1min, resample_1min
    pool = await _get_conn()

    base = datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc)
    records = [
        ("TEST", base + timedelta(minutes=i), 100.0+i, 101.0+i, 99.0+i, 100.5+i, 50000)
        for i in range(10)
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            await insert_bars_1min(conn, records)

    async with pool.acquire() as conn:
        resampled = await resample_1min(conn, "TEST", "5 minutes", base, base + timedelta(minutes=9))
        assert len(resampled) == 2  # 10 min → 2 x 5min buckets

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM price_history_1min WHERE symbol = 'TEST'")


# ═══════════════════════════════════════════════════════════════════════════
# Indicators
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_indicators_insert_and_query():
    from fastapi_app.db.indicators import insert_indicators, get_indicator
    pool = await _get_conn()

    base = datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc)
    records = [
        (base + timedelta(minutes=i), "TEST", "1m", "RSI_14", 50.0 + i, None, None)
        for i in range(5)
    ]

    async with pool.acquire() as conn:
        count = await insert_indicators(conn, records)
    assert count == 5

    async with pool.acquire() as conn:
        values = await get_indicator(conn, "TEST", "RSI_14", "1m", base, base + timedelta(minutes=4))
        assert len(values) == 5
        assert values[0]["value"] == 50.0

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM indicators WHERE symbol = 'TEST'")


@pytest.mark.asyncio(loop_scope="session")
async def test_indicators_multi():
    from fastapi_app.db.indicators import insert_indicators, get_indicators_multi
    pool = await _get_conn()

    base = datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc)
    records = [
        (base, "TEST", "5m", "EMA_8", 100.0, None, None),
        (base, "TEST", "5m", "EMA_21", 99.5, None, None),
        (base, "TEST", "5m", "RSI_14", 55.0, None, None),
    ]

    async with pool.acquire() as conn:
        await insert_indicators(conn, records)

    async with pool.acquire() as conn:
        results = await get_indicators_multi(conn, "TEST", ["EMA_8", "EMA_21"], "5m", base, base)
        assert len(results) == 2
        names = {r["indicator_name"] for r in results}
        assert names == {"EMA_8", "EMA_21"}

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM indicators WHERE symbol = 'TEST'")


# ═══════════════════════════════════════════════════════════════════════════
# Signals
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_signals_insert_and_query():
    from fastapi_app.db.strategies import create_strategy
    from fastapi_app.db.signals import insert_signal, get_signals
    pool = await _get_conn()

    async with pool.acquire() as conn:
        strat = await create_strategy(conn, name="test_signal_strat_05")

    async with pool.acquire() as conn:
        signal_id = await insert_signal(
            conn,
            symbol="TEST",
            signal_type="ENTRY_LONG",
            price=195.50,
            strategy_id=strat["id"],
            timeframe="5m",
            confidence=0.85,
            metadata={"reason": "EMA cross"},
        )
    assert signal_id > 0

    async with pool.acquire() as conn:
        signals = await get_signals(conn, "TEST")
        assert len(signals) >= 1
        found = [s for s in signals if s["id"] == signal_id][0]
        assert found["strategy_name"] == "test_signal_strat_05"
        assert found["confidence"] == pytest.approx(0.85, abs=0.01)

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM signals WHERE id = $1", signal_id)
        await conn.execute("DELETE FROM strategies WHERE id = $1", strat["id"])


# ═══════════════════════════════════════════════════════════════════════════
# Backtest Runs
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio(loop_scope="session")
async def test_backtest_save_and_query():
    from fastapi_app.db.strategies import create_strategy, save_backtest, get_backtests
    pool = await _get_conn()

    async with pool.acquire() as conn:
        strat = await create_strategy(conn, name="test_bt_strat_06")

    async with pool.acquire() as conn:
        bt_id = await save_backtest(
            conn,
            strategy_id=strat["id"],
            symbol="SPY",
            timeframe="1D",
            start_date=date(2023, 1, 1),
            end_date=date(2024, 1, 1),
            parameters={"fast": 8, "slow": 21},
            metrics={
                "total_trades": 42,
                "win_rate": 0.5714,
                "profit_factor": 1.82,
                "net_pnl": 12500.00,
                "max_drawdown": 0.085,
                "sharpe_ratio": 1.45,
            },
            notes="Test backtest run",
        )
    assert bt_id > 0

    async with pool.acquire() as conn:
        backtests = await get_backtests(conn, strategy_id=strat["id"])
        assert len(backtests) == 1
        bt = backtests[0]
        assert bt["strategy_name"] == "test_bt_strat_06"
        assert bt["total_trades"] == 42
        assert float(bt["win_rate"]) == pytest.approx(0.5714, abs=0.001)

    # Cleanup
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM backtest_runs WHERE id = $1", bt_id)
        await conn.execute("DELETE FROM strategies WHERE id = $1", strat["id"])
