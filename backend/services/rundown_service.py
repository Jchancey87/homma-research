"""
backend/services/rundown_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Core business logic for the Daily Market Rundown workflow.
Aggregates macro context, curated RSS news feeds, daily gainers/movers,
live index quotes, and optional morning research email text to synthesize
a structured Daily Market Rundown via the LLM facade.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, date as date_cls, timezone
from typing import Optional

import asyncpg

from fastapi_app.db import rundown as db_rundown
from services.live_quotes_service import get_live_quotes
from llm.llm_client import get_daily_rundown
from validation import EASTERN_TZ

log = logging.getLogger(__name__)


async def get_or_generate_rundown(
    conn: asyncpg.Connection,
    target_date: Optional[date_cls] = None,
    raw_email_text: Optional[str] = None,
    force_refresh: bool = False,
) -> dict:
    """
    Get cached Daily Market Rundown for target_date (defaults to today ET).
    If missing or force_refresh is True, generates a new rundown and saves it.
    """
    if target_date is None:
        target_date = datetime.now(EASTERN_TZ).date()

    if not force_refresh and not raw_email_text:
        existing = await db_rundown.get_daily_rundown_by_date(conn, target_date)
        if existing:
            log.info("[rundown_service] Returning cached rundown for %s", target_date)
            return existing

    return await generate_and_save_rundown(conn, target_date, raw_email_text)


async def generate_and_save_rundown(
    conn: asyncpg.Connection,
    target_date: date_cls,
    raw_email_text: Optional[str] = None,
) -> dict:
    """
    Gather market data from DB, live quotes, and RSS feed, synthesize via LLM,
    and persist the resulting Daily Market Rundown to the DB.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    log.info("[rundown_service] Generating Daily Market Rundown for %s", date_str)

    # 1. Fetch live index quotes (SPY, QQQ, IWM, VIX, ^TNX)
    index_tickers = ["SPY", "QQQ", "IWM", "^VIX", "^TNX"]
    quotes_map = {}
    try:
        raw_quotes = await get_live_quotes(index_tickers)
        for t, q in raw_quotes.items():
            quotes_map[t] = {
                "last_price": q.last_price,
                "change_pct": q.change_pct,
                "volume": q.volume,
            }
    except Exception as e:
        log.warning("[rundown_service] Failed to fetch live index quotes: %s", e)

    # 2. Fetch curated RSS articles from today / recent
    curated_rows = await conn.fetch(
        "SELECT title, description, link, published_at, associated_tickers, curated_notes "
        "FROM curated_rss_items ORDER BY published_at DESC LIMIT 30"
    )
    rss_feed_items = [
        {
            "title": r["title"],
            "description": r["description"][:300] if r["description"] else "",
            "tickers": r["associated_tickers"],
            "published_at": r["published_at"].isoformat() if r["published_at"] else "",
        }
        for r in curated_rows
    ]

    # 3. Fetch top gainers / pre-market movers for the target date
    gainers_rows = await conn.fetch(
        "SELECT ticker, gap_pct, float_shares, rvol_15m, sector, market_cap, "
        "news_headline, close_price, open_price, prev_close, "
        "COALESCE(extended_change_pct, gap_pct, 0) AS extended_change_pct "
        "FROM daily_gainers WHERE date = $1 "
        "ORDER BY COALESCE(extended_change_pct, gap_pct, 0) DESC LIMIT 15",
        date_str,
    )

    top_gainers = [
        {
            "ticker": r["ticker"],
            "gap_pct": float(r["gap_pct"]) if r["gap_pct"] is not None else None,
            "extended_change_pct": float(r["extended_change_pct"]) if r["extended_change_pct"] is not None else None,
            "float_shares": r["float_shares"],
            "rvol": float(r["rvol_15m"]) if r["rvol_15m"] is not None else None,
            "sector": r["sector"],
            "price": float(r["close_price"]) if r["close_price"] is not None else None,
            "headline": r["news_headline"],
        }
        for r in gainers_rows
    ]

    # 4. Assemble payload
    market_payload = {
        "date": date_str,
        "index_quotes": quotes_map,
        "top_movers": top_gainers,
        "recent_curated_news": rss_feed_items,
    }

    # 5. Invoke LLM client in thread
    def _run_llm():
        content_md, model_used = get_daily_rundown(date_str, market_payload, raw_email_text)
        return content_md

    rundown_md = await asyncio.to_thread(_run_llm)

    # 6. Save to DB
    saved = await db_rundown.save_daily_rundown(
        conn,
        target_date=target_date,
        content=rundown_md,
        raw_source=raw_email_text,
    )
    log.info("[rundown_service] Rundown for %s saved to database (ID=%d)", date_str, saved["id"])
    return saved
