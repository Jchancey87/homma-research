import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytz
from validation import EASTERN_TZ

from momentum_screener.schwab.stream_client import SchwabStreamer

@pytest.mark.asyncio
async def test_load_fundamentals_queries_close_and_short_int_float():
    """Verify load_fundamentals queries and caches close and short_int_float."""
    streamer = SchwabStreamer()
    mock_conn = AsyncMock()
    
    mock_daily_rows = [
        {'symbol': 'AAPL', 'high': 150.0, 'close': 148.0}
    ]
    mock_fund_rows = [
        {
            'symbol': 'AAPL', 'shares_outstanding': 10000000, 'market_cap': 1500000000,
            'pe_ratio': 15.0, 'dividend_yield': 1.5, 'vol_10d_avg': 500000,
            'high_52wk': 160.0, 'low_52wk': 120.0, 'float_category': 'Low-Float',
            'short_int_float': 5.2
        }
    ]
    
    async def mock_fetch(query, *args):
        if 'price_history_daily' in query:
            return mock_daily_rows
        elif 'stock_fundamentals' in query:
            return mock_fund_rows
        return []
        
    mock_conn.fetch = mock_fetch
    
    mock_db_pool = MagicMock()
    mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
    streamer.db_pool = mock_db_pool
    
    await streamer.load_fundamentals(['AAPL'])
    
    assert 'AAPL' in streamer.fundamentals_cache
    cached = streamer.fundamentals_cache['AAPL']
    assert cached['yesterday_close'] == 148.0
    assert cached['yesterday_high'] == 150.0
    assert cached['short_int_float'] == 5.2


@pytest.mark.asyncio
async def test_evaluate_and_fire_alert_computes_gap_pct_with_yesterday_close():
    """Verify gap_pct calculation uses yesterday_close in evaluate_and_fire_alert."""
    streamer = SchwabStreamer()
    streamer.current_date = datetime.now(EASTERN_TZ).date()
    streamer.fundamentals_cache['AAPL'] = {
        'yesterday_close': 100.0,
        'yesterday_high': 105.0,
        'vol_10d_avg': 1000000,
        'shares_outstanding': 50000000,
    }
    
    streamer.check_and_fire_alert = AsyncMock()
    
    streamer.completed_bars_1m['AAPL'] = [
        {'volume': 50000, 'open': 102.0, 'close': 104.0}
    ]
    
    # We call evaluate_and_fire_alert with open_price=103.0 (so gap_pct should be (103.0 - 100.0) / 100.0 * 100.0 = 3.0%)
    await streamer.evaluate_and_fire_alert(
        symbol='AAPL',
        last_price=104.0,
        total_volume=5000000,
        high_price=103.0,
        low_price=101.0,
        open_price=103.0
    )
    
    assert streamer.check_and_fire_alert.called
    args = streamer.check_and_fire_alert.call_args[0]
    gap_pct = args[4]
    assert gap_pct == 3.0


@pytest.mark.asyncio
@patch('fastapi_app.tasks.alerts.httpx.post')
@patch('database.get_connection')
async def test_send_telegram_alert_task_updates_sent_status(mock_get_connection, mock_post):
    """Verify send_telegram_alert_task updates DB sent status after successful Telegram delivery."""
    from fastapi_app.tasks.alerts import send_telegram_alert_task
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp
    
    mock_conn = MagicMock()
    mock_get_connection.return_value.__enter__.return_value = mock_conn
    
    payload = {
        "symbol": "AAPL",
        "price": 150.25,
        "alert_type": "HOD_BREAKOUT",
        "rvol": 3.5,
        "time": "2026-06-14T14:30:00.000000",
        "alert_db_id": 42,
        "alert_db_time": "2026-06-14T14:30:00.000000"
    }
    
    result = send_telegram_alert_task(payload)
    
    assert result["status"] == "success"
    assert mock_conn.execute.called
    sql_args = mock_conn.execute.call_args[0]
    assert "UPDATE screener_alerts" in sql_args[0]
    assert "SET sent = TRUE" in sql_args[0]
    params = sql_args[1]
    assert params[0] == 42
    assert params[1] == datetime.fromisoformat("2026-06-14T14:30:00.000000")


@pytest.mark.asyncio
async def test_alert_min_pct_increase_wired_to_price_buckets():
    """Verify ALERT_MIN_PCT_INCREASE is wired to price buckets in check_and_fire_alert."""
    from momentum_screener.schwab.stream_client import ALERT_MIN_PCT_INCREASE
    
    streamer = SchwabStreamer()
    streamer.watchlist_symbols = {'AAPL'}
    streamer.fundamentals_cache['AAPL'] = {
        'shares_outstanding': 10000000,
        'vol_10d_avg': 500000,
    }
    
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 'OK'
    mock_conn.fetchrow.return_value = {'id': 42, 'alert_time': datetime.now()}
    
    mock_db_pool = MagicMock()
    mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
    streamer.db_pool = mock_db_pool
    
    with patch('momentum_screener.schwab.stream_client.redis_client'), \
         patch('momentum_screener.schwab.stream_client.celery_app'):
         
         await streamer.check_and_fire_alert(
             symbol='AAPL',
             last_price=10.0,
             total_volume=1000000,
             rvol=2.0,
             gap_pct=1.5,
             alert_type='VOLUME_SPIKE'
         )
         
    assert mock_conn.fetchval.called
    call_args = mock_conn.fetchval.call_args[0]
    assert call_args[7] == ALERT_MIN_PCT_INCREASE


@pytest.mark.asyncio
async def test_save_alert_to_db_inserts_short_int_float():
    """Verify save_alert_to_db inserts short_int_float parameter."""
    streamer = SchwabStreamer()
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {'id': 42, 'alert_time': datetime.now()}
    
    mock_db_pool = MagicMock()
    mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn
    streamer.db_pool = mock_db_pool
    
    await streamer.save_alert_to_db(
        symbol='AAPL',
        price=150.25,
        volume=1000000,
        rvol=2.5,
        gap_pct=3.4,
        float_shares=50000000,
        alert_type='HOD_BREAKOUT',
        short_int_float=12.5
    )
    
    assert mock_conn.fetchrow.called
    sql_args = mock_conn.fetchrow.call_args[0]
    query = sql_args[0]
    params = sql_args[1:]
    
    assert "INSERT INTO screener_alerts" in query
    assert "short_int_float" in query
    assert params[0] == 'AAPL'
    assert params[1] == 150.25
    assert params[2] == 1000000
    assert params[3] == 2.5
    assert params[4] == 3.4
    assert params[5] == 12.5
    assert params[6] == 50000000
    assert params[7] == 'HOD_BREAKOUT'
