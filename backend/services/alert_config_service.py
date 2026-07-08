"""
services/alert_config_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Caching service wrapper around db/alert_config.py CRUD.
Caches settings in-memory with a 30-second TTL.
"""
from __future__ import annotations

import time
import json
import logging
import asyncpg
from fastapi_app.db.alert_config import (
    fetch_alert_configs,
    update_alert_config,
    fetch_alert_scoring_configs,
    update_alert_scoring_config
)

log = logging.getLogger(__name__)

# Keep legacy methods for backward compatibility
_config_cache: dict | None = None
_config_cache_time: float = 0.0
_TTL: float = 30.0

async def get_cached_alert_config(conn: asyncpg.Connection, key: str = "global_config") -> dict:
    """Fetch configuration, caching it in memory with a 30-second TTL."""
    global _config_cache, _config_cache_time
    now = time.time()
    if _config_cache is None or (now - _config_cache_time) > _TTL:
        scoring = await fetch_alert_scoring_configs(conn)
        configs = await fetch_alert_configs(conn)
        
        # Re-construct the global_config dict format
        enabled = {}
        global_config = {}
        for c in configs:
            at = c["alert_type"]
            enabled[at] = c["enabled"]
            global_config[f"rvol_min_{at}"] = c["rvol_min"]
            global_config[f"cooldown_mins_{at}"] = c["cooldown_mins"]
            
        global_config["enabled_alerts"] = enabled
        for k, v in scoring.items():
            global_config[k] = v
            
        _config_cache = global_config
        _config_cache_time = now
        log.debug("[alert_config_service] Configuration cache refreshed.")
    return _config_cache

async def save_alert_config(conn: asyncpg.Connection, value: dict, key: str = "global_config") -> bool:
    """Save configuration to the DB and update the in-memory cache."""
    value_json = json.dumps(value)
    status = await conn.execute(
        """
        INSERT INTO alert_configs (key, value, updated_at)
        VALUES ($1, $2::jsonb, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, updated_at = NOW()
        """,
        key, value_json
    )
    global _config_cache, _config_cache_time
    if status in ("INSERT 0 1", "UPDATE 1"):
        _config_cache = value
        _config_cache_time = time.time()
        log.info("[alert_config_service] Configuration saved and cache updated.")
        return True
    else:
        log.error("[alert_config_service] Failed to save configuration to database.")
        return False


# New class-based service for test suite compatibility
class AlertConfigService:
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self._scoring_cache = None
        self._configs_cache = None
        self._last_scoring_fetch = 0.0
        self._last_configs_fetch = 0.0
        self._ttl = 30.0

    async def _load_config_from_db(self):
        """Query DB to load configurations."""
        async with self.db_pool.acquire() as conn:
            configs = await fetch_alert_configs(conn)
            scoring = await fetch_alert_scoring_configs(conn)
            return configs, scoring

    async def get_scoring_configs(self) -> dict:
        now = time.time()
        if self._scoring_cache is None or (now - self._last_scoring_fetch) > self._ttl:
            configs, scoring = await self._load_config_from_db()
            self._scoring_cache = scoring
            self._configs_cache = configs
            self._last_scoring_fetch = now
            self._last_configs_fetch = now
        return self._scoring_cache

    async def get_alert_configs(self) -> list[dict]:
        now = time.time()
        if self._configs_cache is None or (now - self._last_configs_fetch) > self._ttl:
            configs, scoring = await self._load_config_from_db()
            self._scoring_cache = scoring
            self._configs_cache = configs
            self._last_scoring_fetch = now
            self._last_configs_fetch = now
        return self._configs_cache
