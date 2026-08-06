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

from validation import EASTERN_TZ

log = logging.getLogger(__name__)

_scheduler = None  # module-level singleton


def _build_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone="UTC")

    # ── Job 1: Nightly gainer ingest ─────────────────────────────────────────
    scheduler.add_job(
        _nightly_gainer_ingest,
        CronTrigger(day_of_week="mon-fri", hour=20, minute=5, timezone=EASTERN_TZ),  # 8:05 PM ET
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
        CronTrigger(day_of_week="mon-fri", hour=9, minute=10, timezone=EASTERN_TZ),  # 9:10 AM ET
        id="premarket_gappers_summary",
        name="Pre-market Gappers Summary",
        replace_existing=True,
    )

    # ── Job 5: Nightly alert chart backfill ──────────────────────────────────
    scheduler.add_job(
        _nightly_alerts_backfill,
        CronTrigger(day_of_week="mon-fri", hour=20, minute=10, timezone=EASTERN_TZ),  # 8:10 PM ET
        id="nightly_alerts_backfill",
        name="Nightly Alerts Backfill",
        replace_existing=True,
        misfire_grace_time=1800,  # 30 min
    )

    # ── Job 6: Update Continuation Play Performance ─────────────────────────
    scheduler.add_job(
        _update_continuation_performance,
        CronTrigger(day_of_week="mon-fri", hour=20, minute=15, timezone=EASTERN_TZ),  # 8:15 PM ET
        id="update_continuation_performance",
        name="Update Continuation Performance",
        replace_existing=True,
        misfire_grace_time=1800,  # 30 min
    )

    # ── Job 7: Ingest RSS Feeds ──────────────────────────────────────────────
    scheduler.add_job(
        _ingest_rss_feeds,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-16",
            minute="*/15",
            timezone=EASTERN_TZ,
        ),  # Every 15 min, 9 AM–4:59 PM ET Mon–Fri
        id="ingest_rss_feeds",
        name="Ingest RSS Feeds",
        replace_existing=True,
    )

    # ── Job 8: Daily Market Rundown ──────────────────────────────────────────
    scheduler.add_job(
        _daily_market_rundown,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone=EASTERN_TZ),  # 8:30 AM ET
        id="daily_market_rundown",
        name="Daily Market Rundown",
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
        eastern = EASTERN_TZ
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
    """Pre-market gappers summary. Telegram removed — placeholder for future channel."""
    log.info("[scheduler] premarket_gappers_summary — Telegram removed, skipping dispatch")



async def _nightly_alerts_backfill() -> None:
    """Run backfill_alert_candles from jobs/backfill_alert_candles.py off-thread."""
    import asyncio

    log.info("[scheduler] nightly_alerts_backfill starting")
    try:
        import pytz
        eastern = EASTERN_TZ
        target_date_obj = datetime.now(eastern).date()

        def _run() -> None:
            import sys, os
            _backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _repo = os.path.dirname(_backend)
            if _repo not in sys.path:
                sys.path.insert(0, _repo)
            if _backend not in sys.path:
                sys.path.insert(0, _backend)
            from jobs.backfill_alert_candles import backfill_alert_candles
            backfill_alert_candles(target_date_obj)

        await asyncio.to_thread(_run)
        log.info("[scheduler] nightly_alerts_backfill done")
    except Exception as exc:
        log.exception("[scheduler] nightly_alerts_backfill failed: %s", exc)


async def _update_continuation_performance() -> None:
    """Run update_all_continuation_performances from services/continuation_performance_service.py off-thread."""
    import asyncio
    log.info("[scheduler] update_continuation_performance starting")
    try:
        def _run() -> int:
            import sys, os
            _backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _repo = os.path.dirname(_backend)
            if _repo not in sys.path:
                sys.path.insert(0, _repo)
            if _backend not in sys.path:
                sys.path.insert(0, _backend)
            from services.continuation_performance_service import update_all_continuation_performances
            return update_all_continuation_performances()

        count = await asyncio.to_thread(_run)
        log.info("[scheduler] update_continuation_performance done — updated %d rows", count)
    except Exception as exc:
        log.exception("[scheduler] update_continuation_performance failed: %s", exc)


async def _ingest_rss_feeds() -> None:
    """Ingest configured RSS feeds and auto-publish all articles to curated feed."""
    log.info("[scheduler] Ingesting RSS feeds starting")
    try:
        from .db import get_pool
        from services import rss_service

        pool = get_pool()
        async with pool.acquire() as conn:
            stats = await rss_service.fetch_and_ingest_feeds(conn)

        log.info(
            "[scheduler] Ingesting RSS feeds done — parsed=%d, auto_approved=%d",
            stats.get("processed", 0), stats.get("auto_approved", 0),
        )
    except Exception as exc:
        log.exception("[scheduler] Ingesting RSS feeds failed: %s", exc)


async def _daily_market_rundown() -> None:
    """Generate and cache pre-market Daily Market Rundown for the trading session."""
    log.info("[scheduler] Daily Market Rundown generation starting")
    try:
        from .db import get_pool
        from services import rundown_service

        pool = get_pool()
        async with pool.acquire() as conn:
            res = await rundown_service.generate_and_save_rundown(conn, datetime.now(EASTERN_TZ).date())

        log.info("[scheduler] Daily Market Rundown generation done — ID=%s", res.get("id"))
    except Exception as exc:
        log.exception("[scheduler] Daily Market Rundown generation failed: %s", exc)



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
