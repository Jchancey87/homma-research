"""
fastapi_app/routers/rss.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
API endpoints for self-hosted curated RSS feeds.
Thin router following RFC-001/RFC-005 conventions:
- No raw SQL inside endpoints.
- Business logic is delegated to services/rss_service.py.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..db import get_db
from ..db import rss as db_rss
from services import rss_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/rss", tags=["rss"])


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class RSSSourceCreate(BaseModel):
    name: str
    feed_url: str
    category: Literal["biotech", "tech", "general"]
    is_active: bool = True


class RSSSourceUpdate(BaseModel):
    name: Optional[str] = None
    feed_url: Optional[str] = None
    category: Optional[Literal["biotech", "tech", "general"]] = None
    is_active: Optional[bool] = None


class RSSCurateBody(BaseModel):
    title: str
    description: str
    associated_tickers: list[str]
    curated_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Feed Source Routes
# ---------------------------------------------------------------------------

@router.get("/sources")
async def list_sources(db: asyncpg.Connection = Depends(get_db)):
    """Get all configured feed sources."""
    return await db_rss.list_rss_sources(db)


@router.post("/sources", status_code=201)
async def create_source(data: RSSSourceCreate, db: asyncpg.Connection = Depends(get_db)):
    """Add a new RSS source feed."""
    try:
        source_id = await db_rss.insert_rss_source(
            db,
            name=data.name,
            feed_url=data.feed_url,
            category=data.category,
            is_active=data.is_active
        )
        return {"id": source_id, "message": "Source added successfully."}
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Feed URL is already configured.")


@router.put("/sources/{source_id}")
async def update_source(source_id: int, data: RSSSourceUpdate, db: asyncpg.Connection = Depends(get_db)):
    """Update a feed source's configuration."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    updated = await db_rss.update_rss_source(db, source_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Feed source not found.")
    return {"message": "Source updated successfully."}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, db: asyncpg.Connection = Depends(get_db)):
    """Remove a feed source."""
    deleted = await db_rss.delete_rss_source(db, source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Feed source not found.")
    return {"message": "Source deleted successfully."}


# ---------------------------------------------------------------------------
# Ingest Feed Queue Routes
# ---------------------------------------------------------------------------

@router.get("/pool")
async def get_pool(status: Optional[str] = "pending", db: asyncpg.Connection = Depends(get_db)):
    """Get the list of raw staging articles."""
    return await db_rss.list_rss_feed_pool(db, status=status, limit=100)


@router.post("/pool/trigger-ingest")
async def trigger_ingest(db: asyncpg.Connection = Depends(get_db)):
    """Manually trigger background feed ingestion and return statistics."""
    stats = await rss_service.fetch_and_ingest_feeds(db)
    # Deliver any pending auto-approved Telegram notifications
    await rss_service.send_pending_telegram_alerts(db)
    return {"message": "Ingest complete", "stats": stats}


@router.post("/pool/{item_id}/curate")
async def curate_item(item_id: int, data: RSSCurateBody, db: asyncpg.Connection = Depends(get_db)):
    """Approve, annotate, and publish an article from the staging pool to the curated feed."""
    item = await db_rss.get_rss_feed_pool_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Staging pool item not found.")
    
    # 1. Add to curated items
    await db_rss.insert_curated_rss_item(
        db,
        pool_item_id=item_id,
        guid=item["guid"],
        title=data.title,
        description=data.description,
        link=item["link"],
        published_at=item["published_at"],
        curated_by="admin",
        associated_tickers=data.associated_tickers,
        curated_notes=data.curated_notes
    )
    
    # 2. Update status in staging pool
    await db_rss.update_rss_feed_pool_status(db, item_id, "approved")
    
    # 3. Deliver Telegram notification synchronously
    await rss_service.send_pending_telegram_alerts(db)
    
    return {"message": "Item published and Telegram alert queued."}


@router.post("/pool/{item_id}/reject")
async def reject_item(item_id: int, db: asyncpg.Connection = Depends(get_db)):
    """Reject and hide an article in the staging pool."""
    updated = await db_rss.update_rss_feed_pool_status(db, item_id, "rejected")
    if not updated:
        raise HTTPException(status_code=404, detail="Staging pool item not found.")
    return {"message": "Item rejected."}


# ---------------------------------------------------------------------------
# Public RSS Syndication Feed
# ---------------------------------------------------------------------------

@router.get("/feed")
async def get_rss_feed(db: asyncpg.Connection = Depends(get_db)):
    """Public RSS 2.0 XML feed (enriched with live quotes)."""
    xml_content = await rss_service.generate_rss_xml(db)
    return Response(content=xml_content, media_type="application/rss+xml")
