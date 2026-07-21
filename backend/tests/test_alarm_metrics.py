import pytest
from datetime import datetime, date
import asyncpg
from fastapi_app.db import get_pool
from services.alarm_metrics_service import (
    compute_hourly_metrics,
    compute_daily_rollup,
    save_alarm_metrics,
    get_alarm_rate_trend,
    get_bad_actors,
    get_chattering_alerts,
)
from validation import EASTERN_TZ

@pytest.mark.asyncio(loop_scope="session")
async def test_alarm_metrics_service_and_routes(client):
    """
    Test alarm metrics service and API endpoints.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        # 1. Clean up metrics and insert mock alerts for target date
        target_date = date(2026, 7, 15)
        
        # Delete existing data for clean tests
        await conn.execute("DELETE FROM alerts.alarm_metrics WHERE metric_date = $1", target_date)
        await conn.execute("DELETE FROM public.screener_alerts WHERE alert_time::date = $1", target_date)
        
        # Insert mock alerts at different times of the day
        # Hour 10: 2 alerts (1 helpful)
        dt_10_1 = EASTERN_TZ.localize(datetime(2026, 7, 15, 10, 5, 0))
        dt_10_2 = EASTERN_TZ.localize(datetime(2026, 7, 15, 10, 15, 0))
        # Hour 14: 4 alerts (chattering on AAPL HOD_BREAKOUT)
        dt_14_1 = EASTERN_TZ.localize(datetime(2026, 7, 15, 14, 1, 0))
        dt_14_2 = EASTERN_TZ.localize(datetime(2026, 7, 15, 14, 1, 15))
        dt_14_3 = EASTERN_TZ.localize(datetime(2026, 7, 15, 14, 1, 30))
        dt_14_4 = EASTERN_TZ.localize(datetime(2026, 7, 15, 14, 1, 45))
        
        # Insert alerts
        await conn.execute(
            """
            INSERT INTO public.screener_alerts (
                symbol, alert_time, trigger_price, trigger_volume, rel_vol, gap_pct, alert_type, priority_tier, feedback_score
            ) VALUES 
            ('AAPL', $1, 150.0, 10000, 2.5, 3.2, 'HOD_BREAKOUT', 'Tier 1', 'helpful'),
            ('MSFT', $2, 300.0, 5000, 1.8, 1.5, 'VWAP_CROSSOVER', 'Tier 2', 'noise'),
            ('AAPL', $3, 151.0, 20000, 3.0, 3.2, 'HOD_BREAKOUT', 'Tier 3', NULL),
            ('AAPL', $4, 151.2, 21000, 3.1, 3.2, 'HOD_BREAKOUT', 'Tier 3', NULL),
            ('AAPL', $5, 151.4, 22000, 3.2, 3.2, 'HOD_BREAKOUT', 'Tier 3', NULL),
            ('AAPL', $6, 151.6, 23000, 3.3, 3.2, 'HOD_BREAKOUT', 'Tier 3', NULL)
            """,
            dt_10_1, dt_10_2, dt_14_1, dt_14_2, dt_14_3, dt_14_4
        )

        # 2. Test compute_hourly_metrics
        # Test Hour 10
        m_10 = await compute_hourly_metrics(conn, target_date, 10)
        assert m_10["total_alarms"] == 2
        assert m_10["tier1_count"] == 1
        assert m_10["tier2_count"] == 1
        assert m_10["tier3_count"] == 0
        assert m_10["unique_tickers"] == 2
        assert m_10["chattering_count"] == 0
        assert m_10["noise_count"] == 1
        assert m_10["helpful_count"] == 1
        assert m_10["snr_pct"] == 50.0

        # Test Hour 14 (Chattering)
        m_14 = await compute_hourly_metrics(conn, target_date, 14)
        assert m_14["total_alarms"] == 4
        assert m_14["tier3_count"] == 4
        assert m_14["unique_tickers"] == 1
        assert m_14["chattering_count"] == 4  # AAPL fired 4 times in minute 1

        # Test Hour 12 (Empty)
        m_12 = await compute_hourly_metrics(conn, target_date, 12)
        assert m_12["total_alarms"] == 0

        # Save metrics to DB
        await save_alarm_metrics(conn, m_10)
        await save_alarm_metrics(conn, m_14)
        
        # 3. Test compute_daily_rollup
        rollup = await compute_daily_rollup(conn, target_date)
        assert rollup["total_alarms"] == 6
        assert rollup["tier1_count"] == 1
        assert rollup["tier2_count"] == 1
        assert rollup["tier3_count"] == 4
        assert rollup["unique_tickers"] == 2
        assert rollup["chattering_count"] == 4
        
        await save_alarm_metrics(conn, rollup)

        # 4. Test trend and bad actors queries
        trend = await get_alarm_rate_trend(conn, days=30)
        assert len(trend) >= 1
        assert any(t["date"] == "2026-07-15" for t in trend)
        
        bad_actors = await get_bad_actors(conn, days=30, top_n=5)
        assert len(bad_actors) >= 1
        assert bad_actors[0]["symbol"] == "AAPL"
        assert bad_actors[0]["fire_count"] == 5

        chattering = await get_chattering_alerts(conn, target_date)
        assert len(chattering) == 1
        assert chattering[0]["symbol"] == "AAPL"
        assert chattering[0]["fire_count"] == 4

    # 5. Test API endpoints via client
    resp = await client.get("/api/alerts/alarm-metrics?days=30")

    assert resp.status_code == 200
    metrics_data = resp.json()
    assert isinstance(metrics_data, list)
    assert len(metrics_data) >= 1
    assert any(m["date"] == "2026-07-15" for m in metrics_data)

    resp = await client.get("/api/alerts/bad-actors?days=30&top_n=10")
    assert resp.status_code == 200
    bad_actors_data = resp.json()
    assert isinstance(bad_actors_data, list)
    assert len(bad_actors_data) >= 1
    assert any(b["symbol"] == "AAPL" for b in bad_actors_data)

