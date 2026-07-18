"""
fastapi_app/db/alert_config.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CRUD database helpers for alert configurations.
"""
from __future__ import annotations

import json
import logging
import asyncpg

log = logging.getLogger(__name__)

async def fetch_alert_configs(conn: asyncpg.Connection) -> list[dict]:
    """Fetch all alert type configurations, parsed as a list of dicts."""
    row = await conn.fetchrow("SELECT value FROM alert_configs WHERE key = 'global_config'")
    if not row:
        return []
    val = row['value']
    if isinstance(val, str):
        val = json.loads(val)
    enabled_alerts = val.get("enabled_alerts", {})
    
    # We build a list of configuration objects for all alert types
    alert_types = [
        "VOLATILITY_HALT", "VOLATILITY_RESUME", "NEAR_HOD_RADAR", "VOLUME_SPIKE", 
        "PREV_DAY_BREAKOUT", "VWAP_CROSSOVER", "VWAP_BOUNCE", "RUNNING_UP", 
        "BULL_FLAG", "MULTI_TF_CONFLUENCE", "HALT_RESUME_MOMENTUM"
    ]
    
    configs = []
    for at in alert_types:
        configs.append({
            "alert_type": at,
            "enabled": enabled_alerts.get(at, True),
            "rvol_min": val.get(f"rvol_min_{at}", 3.0),
            "cooldown_mins": val.get(f"cooldown_mins_{at}", val.get("alert_min_time_cooldown_mins", 2))
        })
    return configs

async def update_alert_config(conn: asyncpg.Connection, alert_type: str, data: dict) -> bool:
    """Update an alert type's parameters inside the global config."""
    row = await conn.fetchrow("SELECT value FROM alert_configs WHERE key = 'global_config'")
    if not row:
        return False
    val = row['value']
    if isinstance(val, str):
        val = json.loads(val)
        
    enabled_alerts = val.setdefault("enabled_alerts", {})
    if "enabled" in data:
        enabled_alerts[alert_type] = bool(data["enabled"])
    if "rvol_min" in data:
        val[f"rvol_min_{alert_type}"] = float(data["rvol_min"])
    if "cooldown_mins" in data:
        val[f"cooldown_mins_{alert_type}"] = int(data["cooldown_mins"])
        if alert_type == "NEAR_HOD_RADAR":
            val["alert_min_time_cooldown_mins"] = int(data["cooldown_mins"])
            
    status = await conn.execute(
        "UPDATE alert_configs SET value = $1::jsonb, updated_at = NOW() WHERE key = 'global_config'",
        json.dumps(val)
    )
    return status == "UPDATE 1"

async def fetch_alert_scoring_configs(conn: asyncpg.Connection) -> dict:
    """Fetch alert scoring configurations as a flat key-value dictionary."""
    row = await conn.fetchrow("SELECT value FROM alert_configs WHERE key = 'global_config'")
    if not row:
        return {}
    val = row['value']
    if isinstance(val, str):
        val = json.loads(val)
    
    scoring = {
        "tier1_threshold": val.get("tier_1_threshold", 75),
        "tier2_threshold": val.get("tier_2_threshold", 45),
        "tier_1_threshold": val.get("tier_1_threshold", 75),
        "tier_2_threshold": val.get("tier_2_threshold", 45),
        "watchlist_boost": val.get("watchlist_presence_weight", 20),
        "watchlist_presence_weight": val.get("watchlist_presence_weight", 20),
        "watchlist_priority_tag_weight": val.get("watchlist_priority_tag_weight", 20),
        "catalyst_confirmed_weight": val.get("catalyst_confirmed_weight", 25),
        "catalyst_speculative_weight": val.get("catalyst_speculative_weight", 15),
        "catalyst_technical_weight": val.get("catalyst_technical_weight", 10),
        "float_micro_weight": val.get("float_micro_weight", 20),
        "float_low_weight": val.get("float_low_weight", 15),
        "float_mid_weight": val.get("float_mid_weight", 10),
        "session_regular_weight": val.get("session_regular_weight", 15),
        "session_pre_weight": val.get("session_pre_weight", 10),
        "session_post_weight": val.get("session_post_weight", 5),
        "alert_high_weight": val.get("alert_high_weight", 15),
        "alert_mid_weight": val.get("alert_mid_weight", 10),
        "alert_low_weight": val.get("alert_low_weight", 5),
        "rvol_high_weight": val.get("rvol_high_weight", 15),
        "rvol_mid_weight": val.get("rvol_mid_weight", 10),
        "rvol_low_weight": val.get("rvol_low_weight", 5),
    }
    
    for k, v in val.items():
        if k not in scoring and k != "enabled_alerts":
            scoring[k] = v
            
    return scoring

async def update_alert_scoring_config(conn: asyncpg.Connection, key: str, value: float) -> bool:
    """Update a specific scoring weight or threshold parameter."""
    row = await conn.fetchrow("SELECT value FROM alert_configs WHERE key = 'global_config'")
    if not row:
        return False
    val = row['value']
    if isinstance(val, str):
        val = json.loads(val)
        
    db_key = key
    if key == "tier1_threshold":
        db_key = "tier_1_threshold"
    elif key == "tier2_threshold":
        db_key = "tier_2_threshold"
    elif key == "watchlist_boost":
        db_key = "watchlist_presence_weight"
        
    val[db_key] = value
    if db_key == "tier_1_threshold":
        val["tier1_threshold"] = value
    elif db_key == "tier_2_threshold":
        val["tier2_threshold"] = value
    elif db_key == "watchlist_presence_weight":
        val["watchlist_boost"] = value
        
    status = await conn.execute(
        "UPDATE alert_configs SET value = $1::jsonb, updated_at = NOW() WHERE key = 'global_config'",
        json.dumps(val)
    )
    return status == "UPDATE 1"
