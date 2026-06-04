"""
fastapi_app/scheduler.py
APScheduler (asyncio backend) integration for Phase 3.

Registered jobs:
  1. nightly_gainer_ingest  — 4:15 PM ET Mon-Fri
  2. expire_continuation_picks — daily at midnight UTC (keeps active list clean)
  3. research_cache_refresh  — placeholder (research router not yet ported)

Start/stop is hooked into the FastAPI lifespan in main.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_scheduler = None  # module-level singleton


def _build_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone="UTC")

    # ── Job 1: Nightly gainer ingest ─────────────────────────────────────────
    scheduler.add_job(
        _nightly_gainer_ingest,
        CronTrigger(day_of_week="mon-fri", hour=20, minute=5, timezone="US/Eastern"),  # 8:05 PM ET
        id="nightly_gainer_ingest",
        name="Nightly Gainer Ingest",
        replace_existing=True,
        misfire_grace_time=1800,  # 30 min
    )

    # ── Job 2: Expire stale continuation picks ───────────────────────────────
    scheduler.add_job(
        _expire_continuation_picks,
        CronTrigger(hour=4, minute=0, timezone="UTC"),  # 4 AM UTC daily
        id="expire_continuation_picks",
        name="Expire Continuation Picks",
        replace_existing=True,
    )

    # ── Job 3: Research cache refresh (placeholder) ───────────────────────────
    scheduler.add_job(
        _research_cache_refresh,
        CronTrigger(hour=5, minute=0, timezone="UTC"),  # 5 AM UTC daily
        id="research_cache_refresh",
        name="Research Cache Refresh",
        replace_existing=True,
    )

    # ── Job 4: Pre-market gappers summary ─────────────────────────────────────
    scheduler.add_job(
        _premarket_gappers_summary,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=10, timezone="US/Eastern"),  # 9:10 AM ET
        id="premarket_gappers_summary",
        name="Pre-market Gappers Summary",
        replace_existing=True,
    )

    return scheduler


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

async def _nightly_gainer_ingest() -> None:
    """Run fetch_gainers + write_gainers from jobs/ingest_gainers.py off-thread."""
    import asyncio

    log.info("[scheduler] nightly_gainer_ingest starting")
    try:
        import pytz
        eastern = pytz.timezone("US/Eastern")
        target_date = datetime.now(eastern).strftime("%Y-%m-%d")

        def _run() -> tuple[int, int]:
            import sys, os
            _backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _repo = os.path.dirname(_backend)
            if _repo not in sys.path:
                sys.path.insert(0, _repo)
            if _backend not in sys.path:
                sys.path.insert(0, _backend)
            from jobs.ingest_gainers import fetch_gainers, write_gainers
            gainers = fetch_gainers(target_date)
            if not gainers:
                log.warning("[scheduler] No gainers met criteria for %s", target_date)
                return 0, 0
            return write_gainers(gainers, target_date)

        inserted, skipped = await asyncio.to_thread(_run)
        log.info(
            "[scheduler] nightly_gainer_ingest done — inserted=%d skipped=%d date=%s",
            inserted, skipped, target_date,
        )
    except Exception as exc:
        log.exception("[scheduler] nightly_gainer_ingest failed: %s", exc)


async def _expire_continuation_picks() -> None:
    """Deactivate continuation picks older than 3 trading days."""
    log.info("[scheduler] expire_continuation_picks starting")
    try:
        from .db import get_pool

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE continuation_picks
                   SET is_active = FALSE,
                       deactivated_at = NOW(),
                       deactivated_reason = 'auto-expired (>3 days)'
                   WHERE is_active = TRUE
                     AND date::date < (CURRENT_DATE - INTERVAL '3 days')"""
            )
        # result is e.g. "UPDATE 5"
        count = result.split()[-1] if result else "?"
        log.info("[scheduler] expire_continuation_picks — deactivated %s rows", count)
    except Exception as exc:
        log.exception("[scheduler] expire_continuation_picks failed: %s", exc)


async def _research_cache_refresh() -> None:
    """Placeholder — research router not yet ported (Phase 4)."""
    log.info("[scheduler] research_cache_refresh — placeholder, skipping (Phase 4)")


async def _premarket_gappers_summary() -> None:
    """Query pre-market gappers from TV, filter by rules, and broadcast via Telegram."""
    log.info("[scheduler] premarket_gappers_summary starting")
    try:
        import pytz
        import httpx
        from fastapi_app.config import settings
        from services.schwab_client import _get_tradingview_candidates

        token = settings.telegram_bot_token
        chat_id = settings.telegram_chat_id

        if not token or not chat_id:
            log.warning("[scheduler] Telegram not configured, skipping pre-market gappers summary.")
            return

        # Query candidates (TradingView scan)
        import asyncio
        candidates = await asyncio.to_thread(_get_tradingview_candidates)

        gappers = []
        for sym, val in candidates.items():
            price = val.get("price") or 0.0
            change = val.get("change") or 0.0
            volume = val.get("volume") or 0
            float_shares = val.get("float_shares")

            # Filters:
            # Price $1-$30
            price_ok = 1.00 <= price <= 30.00
            # Float <100M
            float_ok = float_shares is None or float_shares < 100_000_000
            # Volume >50k
            volume_ok = volume > 50_000
            # Gap >4%
            gap_ok = change > 4.0

            if price_ok and float_ok and volume_ok and gap_ok:
                gappers.append((sym, price, change, volume, float_shares))

        gappers.sort(key=lambda x: x[2], reverse=True)

        eastern = pytz.timezone("US/Eastern")
        date_str = datetime.now(eastern).strftime("%Y-%m-%d")

        message = (
            "🌅 *PRE-MARKET GAPPERS SUMMARY* 🌅\n"
            f"Date: {date_str}\n\n"
        )

        if not gappers:
            message += "No gappers matching the criteria today."
        else:
            for sym, price, change, volume, float_shares in gappers:
                float_str = f"{float_shares/1_000_000:.1f}M" if float_shares else "N/A"
                vol_str = f"{volume/1_000:.1f}k" if volume >= 1000 else str(volume)
                escaped_sym = sym.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("`", "\\`")
                message += (
                    f"• [${escaped_sym}](https://www.tradingview.com/chart/?symbol={sym}) | "
                    f"Price: ${price:.2f} | "
                    f"Gap: +{change:.1f}% | "
                    f"Vol: {vol_str} | "
                    f"Float: {float_str}\n"
                )

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        log.info("[scheduler] premarket_gappers_summary completed successfully")
    except Exception as exc:
        log.exception("[scheduler] premarket_gappers_summary failed: %s", exc)


# ---------------------------------------------------------------------------
# Public API — called from lifespan
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    global _scheduler
    _scheduler = _build_scheduler()
    _scheduler.start()
    log.info("[scheduler] APScheduler started with %d jobs", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("[scheduler] APScheduler stopped")
    _scheduler = None
