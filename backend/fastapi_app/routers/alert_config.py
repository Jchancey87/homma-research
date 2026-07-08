"""
fastapi_app/routers/alert_config.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
GET and PUT endpoints for dynamic alert configurations and scoring.
"""
from __future__ import annotations

import logging
import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from fastapi_app.db.alert_config import (
    fetch_alert_configs,
    update_alert_config,
    fetch_alert_scoring_configs,
    update_alert_scoring_config
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/alert-config", tags=["alert-config"])

@router.get("")
async def get_config(db: asyncpg.Connection = Depends(get_db)):
    """Fetch the active global alert configurations as a list of dicts."""
    return await fetch_alert_configs(db)

@router.put("")
async def update_config(data: dict, db: asyncpg.Connection = Depends(get_db)):
    """Update a specific alert type's settings."""
    alert_type = data.get("alert_type")
    if not alert_type:
        raise HTTPException(status_code=400, detail="Missing alert_type parameter")
    success = await update_alert_config(db, alert_type, data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save configuration")
    return {"status": "success"}

@router.get("/scoring")
async def get_scoring_config(db: asyncpg.Connection = Depends(get_db)):
    """Fetch the active scoring weights and thresholds."""
    return await fetch_alert_scoring_configs(db)

@router.put("/scoring")
async def update_scoring(data: dict, db: asyncpg.Connection = Depends(get_db)):
    """Update a specific scoring weight or threshold parameter."""
    key = data.get("key")
    value = data.get("value")
    if key is None or value is None:
        raise HTTPException(status_code=400, detail="Missing key or value parameter")
    success = await update_alert_scoring_config(db, key, value)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save scoring configuration")
    return {"status": "success"}
