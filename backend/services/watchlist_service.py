"""
backend/services/watchlist_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Service for watchlist bulk import and export operations.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from typing import List, Dict, Any, Tuple, Optional

import asyncpg
from fastapi_app.db import watchlist as db_watchlist
from validation import normalize_ticker

log = logging.getLogger(__name__)

async def export_watchlist_to_csv(conn: asyncpg.Connection, group_id: Optional[int] = None) -> str:
    """
    Exports the current watchlist to a CSV string.
    """
    rows = await db_watchlist.list_watchlist(conn, group_id=group_id)
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["ticker", "sector", "notes", "tags"])
    
    for r in rows:
        ticker = r["ticker"]
        sector = r.get("sector") or ""
        notes = r.get("notes") or ""
        
        # Parse tags from JSON string/list
        tags_raw = r.get("tags")
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except Exception:
                tags_list = []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []
            
        tags_str = ",".join(tags_list)
        writer.writerow([ticker, sector, notes, tags_str])
        
    return output.getvalue()

async def import_watchlist_from_csv(
    conn: asyncpg.Connection,
    csv_content: str,
    group_id: Optional[int] = None,
) -> Tuple[int, int]:
    """
    Parses CSV content and imports/upserts symbols into the watchlist.
    CSV can have headers: ticker, sector, notes, tags
    If no headers or unrecognized headers, treats the first column as ticker.
    
    Returns a tuple of (inserted_count, updated_count).
    """
    existing_tickers = {t.upper() for t in await db_watchlist.list_watchlist_tickers(conn, group_id=group_id)}
    
    # Read CSV
    f = io.StringIO(csv_content)
    # Peek to check if there is a header
    first_line = f.readline()
    f.seek(0)
    
    has_header = False
    if first_line:
        # Common check for header
        parts = [p.strip().lower() for p in first_line.split(",")]
        if "ticker" in parts or "symbol" in parts:
            has_header = True
            
    reader = csv.reader(f)
    
    header_map = {}
    if has_header:
        headers = [h.strip().lower() for h in next(reader)]
        for i, h in enumerate(headers):
            if h in ("ticker", "symbol"):
                header_map["ticker"] = i
            elif h == "sector":
                header_map["sector"] = i
            elif h == "notes":
                header_map["notes"] = i
            elif h in ("tags", "tag"):
                header_map["tags"] = i
    else:
        # Default mapping if no header
        header_map = {"ticker": 0}
        
    inserted = 0
    updated = 0
    
    for row in reader:
        if not row:
            continue
            
        # Extract ticker
        ticker_idx = header_map.get("ticker", 0)
        if ticker_idx >= len(row):
            continue
        raw_ticker = row[ticker_idx].strip()
        if not raw_ticker:
            continue
            
        try:
            ticker = normalize_ticker(raw_ticker)
        except Exception:
            # Fallback if normalize_ticker is strict
            ticker = raw_ticker.upper().strip()
            
        # Extract optional fields
        sector = None
        if "sector" in header_map:
            idx = header_map["sector"]
            if idx < len(row):
                sector = row[idx].strip() or None
                
        notes = None
        if "notes" in header_map:
            idx = header_map["notes"]
            if idx < len(row):
                notes = row[idx].strip() or None
                
        tags_list = []
        if "tags" in header_map:
            idx = header_map["tags"]
            if idx < len(row):
                raw_tags = row[idx].strip()
                if raw_tags:
                    # split by comma, semicolon, or space
                    tags_list = [t.strip() for t in raw_tags.replace(";", ",").split(",") if t.strip()]
                    
        tags_json = json.dumps(tags_list)
        
        # Check if updating or inserting
        is_update = ticker.upper() in existing_tickers
        
        # Perform upsert
        await db_watchlist.upsert_watchlist(
            conn,
            ticker=ticker,
            sector=sector,
            notes=notes,
            tags_json=tags_json,
            group_id=group_id,
        )
        
        if is_update:
            updated += 1
        else:
            inserted += 1
            
    return inserted, updated
