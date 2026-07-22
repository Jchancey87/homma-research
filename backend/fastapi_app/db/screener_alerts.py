"""
fastapi_app/db/screener_alerts.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read/write helpers for the ``screener_alerts`` and
``screener_alerts_archive`` tables.

The heavy analytics (daily summary aggregation, performance scorecard
CTE) live in ``services.alerts_analytics``; this module only owns the
plain CRUD reads/writes the router needs.

Conventions match db/ohlcv.py: every public function takes a live
``asyncpg.Connection`` as the first argument and returns plain
dicts/lists/booleans so routers stay Router-Layer-Rules compliant.
"""
from __future__ import annotations

import datetime
from typing import Optional

import asyncpg


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def list_recent_alerts(
    conn: asyncpg.Connection,
    limit: int = 50,
) -> list[dict]:
    """Return the most recent N screener alerts (newest first)."""
    rows = await conn.fetch(
        """
        SELECT id, symbol, alert_time, trigger_price, trigger_volume,
               rel_vol, gap_pct, float_shares, alert_type, priority_score, priority_tier,
               vwap_dist_pct, hod_dist_pct, catalyst, stop_price, stop_risk_pct,
               suppressed_reason, group_id
        FROM screener_alerts
        ORDER BY alert_time DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


async def list_alert_dates(conn: asyncpg.Connection) -> list[str]:
    """
    Distinct alert dates (Eastern timezone) as ISO YYYY-MM-DD strings,
    newest first.  Empty list if the table is empty.
    """
    rows = await conn.fetch(
        """
        SELECT DISTINCT (alert_time AT TIME ZONE 'America/New_York')::date AS alert_date
        FROM public.screener_alerts
        ORDER BY alert_date DESC
        """
    )
    return [r["alert_date"].isoformat() for r in rows if r["alert_date"]]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def save_alert_feedback(
    conn: asyncpg.Connection,
    *,
    alert_id: int,
    alert_time: datetime.datetime,
    feedback_score: Optional[str],
    feedback_notes: Optional[str],
) -> tuple[bool, bool]:
    """
    Persist feedback for a specific alert to BOTH ``screener_alerts`` and
    ``screener_alerts_archive``.  Returns ``(updated_active, updated_archive)``
    booleans so the router can surface a useful success message.
    """
    active = await conn.execute(
        """
        UPDATE public.screener_alerts
        SET feedback_score = $1, feedback_notes = $2
        WHERE id = $3 AND alert_time = $4
        """,
        feedback_score, feedback_notes, alert_id, alert_time,
    )
    archive = await conn.execute(
        """
        UPDATE public.screener_alerts_archive
        SET feedback_score = $1, feedback_notes = $2
        WHERE id = $3 AND alert_time = $4
        """,
        feedback_score, feedback_notes, alert_id, alert_time,
    )
    return (
        not active.endswith(" 0"),
        not archive.endswith(" 0"),
    )
