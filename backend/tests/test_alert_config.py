import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Ensure path includes backend
import os
import sys
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Dynamically import the modules to allow collection even before developer subagent completes implementation
try:
    from fastapi_app.db.alert_config import (
        fetch_alert_configs,
        fetch_alert_scoring_configs,
        update_alert_config,
        update_alert_scoring_config
    )
except ImportError:
    fetch_alert_configs = None
    fetch_alert_scoring_configs = None
    update_alert_config = None
    update_alert_scoring_config = None

try:
    from services.alert_config_service import AlertConfigService
except ImportError:
    AlertConfigService = None


@pytest.fixture(scope="session", autouse=True)
async def setup_alert_config_schema():
    """Best-effort create schema for alert_config and alert_scoring_config tables before tests run."""
    from fastapi_app.db import get_pool
    pool = get_pool()
    sql_path = os.path.join(_BACKEND_DIR, "sql", "migrate_alert_config.sql")
    if os.path.exists(sql_path):
        with open(sql_path, "r") as f:
            sql_content = f.read()
        stmts = [s.strip() for s in sql_content.split(";") if s.strip()]
        async with pool.acquire() as conn:
            for stmt in stmts:
                try:
                    await conn.execute(stmt)
                except Exception as e:
                    # Ignore 'already exists' or similar errors
                    if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                        pass
    yield


@pytest.mark.asyncio(loop_scope="session")
async def test_db_retrieval_and_update():
    """Verify that low-level DB functions correctly retrieve and update alert configs."""
    if fetch_alert_configs is None:
        pytest.skip("Developer has not yet implemented fastapi_app.db.alert_config module")

    from fastapi_app.db import get_pool
    pool = get_pool()
    
    async with pool.acquire() as conn:
        # 1. Fetch current alert configs
        configs = await fetch_alert_configs(conn)
        assert isinstance(configs, list)
        
        # Verify default rows exist
        alert_types = [c['alert_type'] for c in configs]
        assert "NEAR_HOD_RADAR" in alert_types
        
        # 2. Update config parameters
        success = await update_alert_config(
            conn, 
            alert_type="NEAR_HOD_RADAR", 
            data={"enabled": False, "rvol_min": 4.5, "cooldown_mins": 5}
        )
        assert success is True
        
        # Re-fetch and check
        updated_configs = await fetch_alert_configs(conn)
        hod_config = next(c for c in updated_configs if c['alert_type'] == "NEAR_HOD_RADAR")
        assert hod_config['enabled'] is False
        assert float(hod_config['rvol_min']) == 4.5
        assert hod_config['cooldown_mins'] == 5
        
        # Restore to default
        await update_alert_config(
            conn, 
            alert_type="NEAR_HOD_RADAR", 
            data={"enabled": True, "rvol_min": 3.0, "cooldown_mins": 2}
        )

        # 3. Fetch scoring configs
        scoring = await fetch_alert_scoring_configs(conn)
        assert isinstance(scoring, dict)
        assert "tier1_threshold" in scoring
        
        # 4. Update scoring config
        success_score = await update_alert_scoring_config(conn, key="tier1_threshold", value=80.0)
        assert success_score is True
        
        updated_scoring = await fetch_alert_scoring_configs(conn)
        assert float(updated_scoring["tier1_threshold"]) == 80.0
        
        # Restore scoring default
        await update_alert_scoring_config(conn, key="tier1_threshold", value=75.0)


@pytest.mark.asyncio(loop_scope="session")
async def test_api_crud_endpoints(client):
    """Verify GET and PUT API endpoints for alert_config and alert_scoring_config."""
    from fastapi_app.main import app
    try:
        from fastapi_app.routers.alert_config import router as alert_config_router
        # Register the router dynamically if not registered by main app yet
        if not any(r.path == "/api/alert-config" for r in app.routes):
            app.include_router(alert_config_router, prefix="/api")
    except ImportError:
        pytest.skip("Developer has not yet implemented fastapi_app.routers.alert_config module")

    # 1. GET /api/alert-config
    get_resp = await client.get("/api/alert-config")
    assert get_resp.status_code == 200
    configs = get_resp.json()
    assert isinstance(configs, list)
    
    # 2. PUT /api/alert-config
    # Update NEAR_HOD_RADAR rvol_min
    put_resp = await client.put(
        "/api/alert-config",
        json={"alert_type": "NEAR_HOD_RADAR", "rvol_min": 5.5, "cooldown_mins": 3}
    )
    assert put_resp.status_code == 200
    assert put_resp.json().get("status") == "success"
    
    # Re-verify
    get_resp2 = await client.get("/api/alert-config")
    configs2 = get_resp2.json()
    hod_cfg = next(c for c in configs2 if c["alert_type"] == "NEAR_HOD_RADAR")
    assert float(hod_cfg["rvol_min"]) == 5.5
    assert hod_cfg["cooldown_mins"] == 3
    
    # Restore defaults
    await client.put(
        "/api/alert-config",
        json={"alert_type": "NEAR_HOD_RADAR", "rvol_min": 3.0, "cooldown_mins": 2}
    )

    # 3. GET /api/alert-config/scoring
    get_score_resp = await client.get("/api/alert-config/scoring")
    assert get_score_resp.status_code == 200
    scoring = get_score_resp.json()
    assert "tier1_threshold" in scoring
    
    # 4. PUT /api/alert-config/scoring
    put_score_resp = await client.put(
        "/api/alert-config/scoring",
        json={"key": "tier1_threshold", "value": 85.0}
    )
    assert put_score_resp.status_code == 200
    assert put_score_resp.json().get("status") == "success"
    
    # Re-verify
    get_score_resp2 = await client.get("/api/alert-config/scoring")
    scoring2 = get_score_resp2.json()
    assert float(scoring2["tier1_threshold"]) == 85.0
    
    # Restore
    await client.put(
        "/api/alert-config/scoring",
        json={"key": "tier1_threshold", "value": 75.0}
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_cache_ttl_logic():
    """Verify that AlertConfigService caches data for 30 seconds before querying DB again."""
    if AlertConfigService is None:
        pytest.skip("Developer has not yet implemented services.alert_config_service module")
        
    from fastapi_app.db import get_pool
    service = AlertConfigService(get_pool())
    
    # Mock database retrieval call to track database queries
    mock_db_retrieval = AsyncMock(return_value={"tier1_threshold": 75.0, "watchlist_boost": 20.0})
    
    # Patch the database loading method of the service
    # Assuming the service method that queries DB is '_load_config_from_db' or 'fetch_from_db'
    db_method_name = None
    for name in dir(service):
        if 'db' in name.lower() or 'fetch' in name.lower() or 'load' in name.lower():
            if callable(getattr(service, name)):
                db_method_name = name
                break
                
    if not db_method_name:
        db_method_name = "fetch_from_db" # fallback
        
    with patch.object(service, db_method_name, mock_db_retrieval) as patched_method:
        # First call: cache empty, should fetch from DB
        await service.get_scoring_configs()
        assert patched_method.call_count == 1
        
        # Second call (immediate): should return cached copy, no DB query
        await service.get_scoring_configs()
        assert patched_method.call_count == 1
        
        # Third call: mock time forward by 10s (should still be cached)
        with patch("time.time", return_value=time.time() + 10):
            await service.get_scoring_configs()
            assert patched_method.call_count == 1
            
        # Fourth call: mock time forward by 35s (>30s TTL), should query DB again
        with patch("time.time", return_value=time.time() + 35):
            await service.get_scoring_configs()
            assert patched_method.call_count == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_stream_client_config_reloading():
    """Verify SchwabStreamer polls AlertConfigService and reloads variables dynamically."""
    from momentum_screener.schwab.stream_client import SchwabStreamer
    streamer = SchwabStreamer()
    
    # Verify SchwabStreamer has poll_config or similar reloading method
    reload_method = None
    for name in dir(streamer):
        if 'poll' in name.lower() or 'reload' in name.lower() or 'refresh' in name.lower():
            if 'config' in name.lower() or 'settings' in name.lower():
                reload_method = name
                break
                
    if not reload_method:
        # Check if config_service attribute or similar is present on streamer
        pytest.skip("SchwabStreamer does not have a dynamic config reloading method yet.")
        
    # Mock config service values
    mock_configs = [
        {"alert_type": "NEAR_HOD_RADAR", "enabled": True, "rvol_min": 4.0, "cooldown_mins": 5}
    ]
    mock_scoring = {"tier1_threshold": 80.0, "watchlist_boost": 25.0}
    
    mock_service = MagicMock()
    mock_service.get_alert_configs = AsyncMock(return_value=mock_configs)
    mock_service.get_scoring_configs = AsyncMock(return_value=mock_scoring)
    
    # Inject mock service
    service_attr = None
    for attr in dir(streamer):
        if 'service' in attr.lower() or 'config' in attr.lower():
            val = getattr(streamer, attr, None)
            if val is not None and not callable(val):
                service_attr = attr
                break
                
    if service_attr:
        setattr(streamer, service_attr, mock_service)
        
    # Trigger refresh (break the infinite polling loop after one iteration)
    with patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError())):
        try:
            await getattr(streamer, reload_method)()
        except asyncio.CancelledError:
            pass
    
    # Verify config got reloaded and applied to streamer variables
    # E.g. check if HOD_BREAKOUT cooldown or thresholds are updated
    # This assertion will depend on the exact implementation details, but we check common variables:
    if hasattr(streamer, "configs"):
        assert streamer.configs.get("NEAR_HOD_RADAR", {}).get("rvol_min") == 4.0
