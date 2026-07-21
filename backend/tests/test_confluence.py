import pytest
import asyncio
from datetime import datetime, timedelta
import pytz
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi_app.db import get_pool
from momentum_screener.schwab.stream_client import SchwabStreamer
from validation import EASTERN_TZ

@pytest.mark.asyncio(loop_scope="session")
async def test_calculate_confluence_score():
    """Verify that calculate_confluence_score works correctly for various scenarios and maps to proper tiers."""
    with patch('momentum_screener.schwab.stream_client.get_client'), \
         patch('momentum_screener.schwab.stream_client.StreamClient'):
        client = SchwabStreamer()
        
        # Test Case 1: Max points (Tier 1)
        # Watchlist (20) + Priority tag (20) + Confirmed Catalyst (25) + Micro-Float (20) + Regular Session (15) + NEAR_HOD_RADAR (15) = 115
        client.watchlist_symbols = {"AAPL"}
        client.watchlist_tags = {"AAPL": ["Priority 1"]}
        client.catalyst_tags = {"AAPL": "Confirmed Catalyst"}
        client.fundamentals_cache = {"AAPL": {"float_category": "Micro-Float"}}
        
        # Mock regular session time (10:00 AM NY time)
        now_et = datetime.now(EASTERN_TZ).replace(hour=10, minute=0, second=0, microsecond=0)
        
        score, tier = client.calculate_confluence_score("AAPL", "NEAR_HOD_RADAR", now_et=now_et)
        assert score == 115
        assert tier == "Tier 1"

        # Test Case 2: Mid-tier (Tier 2)
        # Not in watchlist (0) + No priority tag (0) + Speculative (15) + Low-Float (15) + Pre-market (10) + VOLUME_SPIKE (10) = 50
        client.watchlist_symbols = set()
        client.watchlist_tags = {}
        client.catalyst_tags = {"MSFT": "Speculative"}
        client.fundamentals_cache = {"MSFT": {"float_category": "Low-Float"}}
        now_et_pre = datetime.now(EASTERN_TZ).replace(hour=8, minute=0, second=0, microsecond=0)
        
        score, tier = client.calculate_confluence_score("MSFT", "VOLUME_SPIKE", now_et=now_et_pre)
        assert score == 50
        assert tier == "Tier 2"

        # Test Case 3: Low-tier (Tier 3)
        # Not in watchlist (0) + No priority tag (0) + Technical/No News (10) + High-Float (0) + Post-market (5) + VOLATILITY_HALT (5) = 20
        client.watchlist_symbols = set()
        client.watchlist_tags = {}
        client.catalyst_tags = {"TSLA": "Technical / No News"}
        client.fundamentals_cache = {"TSLA": {"float_category": "High-Float"}}
        now_et_post = datetime.now(EASTERN_TZ).replace(hour=17, minute=0, second=0, microsecond=0)
        
        score, tier = client.calculate_confluence_score("TSLA", "VOLATILITY_HALT", now_et=now_et_post)
        assert score == 20
        assert tier == "Tier 3"


@pytest.mark.asyncio(loop_scope="session")
async def test_gate_bypass_and_db_save():
    """Verify watchlist gate bypass in check_and_fire_alert and priority score DB save."""
    with patch('momentum_screener.schwab.stream_client.get_client'), \
         patch('momentum_screener.schwab.stream_client.StreamClient'), \
         patch('momentum_screener.schwab.stream_client.redis_client') as mock_redis, \
         patch('momentum_screener.schwab.stream_client.celery_app') as mock_celery:
         
        client = SchwabStreamer()
        
        # Set up fundamentals cache for a symbol NOT in watchlist
        # Watchlist gate should be bypassed and alert should process
        symbol = "XYZ"
        client.fundamentals_cache = {
            symbol: {
                "shares_outstanding": 10_000_000,
                "float_category": "Micro-Float",
                "market_cap": 50_000_000,
                "yesterday_high": 10.0
            }
        }
        client.watchlist_symbols = set()
        client.watchlist_tags = {}
        client.catalyst_tags = {symbol: "Confirmed Catalyst"}
        
        # Assign a mock database pool to client
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='OK')
        mock_conn.execute = AsyncMock()
        # fetchrow used by save_alert_to_db — return a real dict so json.dumps doesn't fail
        mock_conn.fetchrow = AsyncMock(return_value={'id': 1, 'alert_time': datetime.now()})
        
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_pool.acquire.return_value = mock_ctx
        client.db_pool = mock_pool
        
        # Fire the alert (XYZ is NOT in watchlist)
        fired = await client.check_and_fire_alert(
            symbol=symbol,
            last_price=12.50,
            total_volume=150000,
            rvol=3.5,
            gap_pct=12.0,
            alert_type="NEAR_HOD_RADAR"
        )
        
        # Watchlist gate is bypassed! Should process alert
        assert fired is True
        
        # Verify save_alert_to_db was called (uses fetchrow for the INSERT ... RETURNING)
        assert mock_conn.fetchrow.called
        
        # Inspect fetchrow args to verify priority_score and priority_tier
        args, kwargs = mock_conn.fetchrow.call_args
        insert_query = args[0]
        assert "priority_score" in insert_query
        assert "priority_tier" in insert_query
        
        # Check the values passed (positional params: symbol, price, volume, rvol, gap_pct,
        # short_int_float, float_shares, alert_type, priority_score, priority_tier, ...)
        insert_params = args[1:]
        assert insert_params[0] == symbol
        assert insert_params[1] == 12.50
        assert insert_params[8] >= 60  # minimum score: catalyst (25) + float (20) + breakout (15) = 60
        assert insert_params[9] in ("Tier 1", "Tier 2")


@pytest.mark.asyncio(loop_scope="session")
async def test_real_db_save_confluence():
    """Verify that priority_score and priority_tier are saved correctly to the real database."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Clean up any existing test records
        await conn.execute("DELETE FROM public.screener_alerts WHERE symbol = 'TCON'")
        
        # Save a test alert with priority score and tier
        await conn.execute("""
            INSERT INTO public.screener_alerts (
                symbol, alert_time, trigger_price, trigger_volume,
                rel_vol, gap_pct, float_shares, alert_type, sent,
                priority_score, priority_tier
            ) VALUES ($1, NOW(), $2, $3, $4, $5, $6, $7, FALSE, $8, $9)
        """, 'TCON', 12.34, 100000, 2.5, 5.0, 50000000, 'NEAR_HOD_RADAR', 75, 'Tier 1')
        
        # Query back and verify
        row = await conn.fetchrow("""
            SELECT priority_score, priority_tier 
            FROM public.screener_alerts 
            WHERE symbol = 'TCON' 
            ORDER BY alert_time DESC LIMIT 1
        """)
        assert row is not None
        assert row['priority_score'] == 75
        assert row['priority_tier'] == 'Tier 1'
        
        # Clean up
        await conn.execute("DELETE FROM public.screener_alerts WHERE symbol = 'TCON'")


@pytest.mark.asyncio(loop_scope="session")
async def test_alert_grouping_and_already_in_play_suppression():
    """Verify that multiple alerts triggered on same ticker within 30s share a group_id,
    and lower/equal priority alerts are suppressed under already-in-play rules."""
    with patch('momentum_screener.schwab.stream_client.get_client'), \
         patch('momentum_screener.schwab.stream_client.StreamClient'), \
         patch('momentum_screener.schwab.stream_client.redis_client'), \
         patch('momentum_screener.schwab.stream_client.celery_app'):
         
        streamer = SchwabStreamer()
        
        symbol = "ABCD"
        streamer.fundamentals_cache = {
            symbol: {
                "shares_outstanding": 10_000_000,
                "float_category": "Micro-Float",
                "market_cap": 50_000_000,
                "yesterday_high": 10.0
            }
        }
        
        # Mock DB pool/conn
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='OK')
        mock_conn.fetchrow = AsyncMock(return_value={'id': 1, 'alert_time': datetime.now()})
        
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_ctx
        streamer.db_pool = mock_pool

        # 1. Trigger first alert (Tier 1/2)
        # Bypasses suppression because it's first alert
        res1 = await streamer.check_and_fire_alert(
            symbol=symbol,
            last_price=10.0,
            total_volume=10000,
            rvol=3.0,
            gap_pct=15.0,
            alert_type="VOLUME_SPIKE"
        )
        assert res1 is True
        assert len(streamer.fired_alerts_session[symbol]) == 1
        first_group_id = streamer.ticker_group_ids[symbol][0]
        assert first_group_id is not None
        
        # 2. Trigger second alert within 30 seconds, same price (no 5% move)
        # Should be suppressed as ALREADY_IN_PLAY but share the same group_id
        res2 = await streamer.check_and_fire_alert(
            symbol=symbol,
            last_price=10.1,  # 1% price increase (not 5%)
            total_volume=12000,
            rvol=3.5,
            gap_pct=15.0,
            alert_type="NEAR_HOD_RADAR"
        )

        assert res2 is True
        # Verify it did not add to fired_alerts_session (it was suppressed)
        assert len(streamer.fired_alerts_session[symbol]) == 1
        
        # Verify save_alert_to_db was called with ALREADY_IN_PLAY reason and same group_id
        args, kwargs = mock_conn.fetchrow.call_args
        insert_params = args[1:]
        assert insert_params[15] == "ALREADY_IN_PLAY"
        assert insert_params[16] == first_group_id
        
        # 3. Trigger third alert with >5% price move (e.g. 10.6, which is 6% move from 10.0)
        # Should NOT be suppressed, should share same group_id if within 30s
        res3 = await streamer.check_and_fire_alert(
            symbol=symbol,
            last_price=10.6,
            total_volume=15000,
            rvol=4.0,
            gap_pct=15.0,
            alert_type="NEAR_HOD_RADAR"
        )
        assert res3 is True
        assert len(streamer.fired_alerts_session[symbol]) == 2
        
        args, kwargs = mock_conn.fetchrow.call_args
        insert_params = args[1:]
        assert insert_params[15] is None # not suppressed
        assert insert_params[16] == first_group_id
