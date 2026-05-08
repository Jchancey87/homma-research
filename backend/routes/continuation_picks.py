"""
continuation_picks.py — API routes for the AI Continuation Watch list.

Picks are sourced from the nightly continuation report (parsed by daily_analysis_report.py)
and stored per-date. A pick becomes inactive when:
  - The user manually dismisses it
  - The ticker's next-day gap_pct drops below a configurable threshold (future cron job)
"""
import json
from datetime import datetime, timezone, timedelta
from flask import Blueprint, jsonify, request
from database import get_connection

cont_picks_bp = Blueprint('continuation_picks', __name__)


# ---------------------------------------------------------------------------
# List active picks  (+ recent inactive for context)
# ---------------------------------------------------------------------------

@cont_picks_bp.route('/continuation-picks', methods=['GET'])
def list_picks():
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    limit = int(request.args.get('limit', 50))

    if include_inactive:
        sql = """
            SELECT * FROM continuation_picks
            ORDER BY is_active DESC, date DESC, rank ASC
            LIMIT %s
        """
        params = (limit,)
    else:
        sql = """
            SELECT * FROM continuation_picks
            WHERE is_active = TRUE
            ORDER BY date DESC, rank ASC
            LIMIT %s
        """
        params = (limit,)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Add picks (batch — from nightly job)
# ---------------------------------------------------------------------------

@cont_picks_bp.route('/continuation-picks', methods=['POST'])
def add_picks():
    """
    Accepts either a single pick or a list of picks.
    Each pick: { ticker, date, reason?, gap_pct?, float_shares?, rvol_15m?, sector?, rank? }
    Uses INSERT ... ON CONFLICT DO NOTHING so re-running the nightly job is idempotent.
    """
    data = request.get_json(silent=True) or {}
    picks = data if isinstance(data, list) else [data]

    if not picks:
        return jsonify({'error': 'No picks provided'}), 400

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with get_connection() as conn:
        for p in picks:
            ticker = (p.get('ticker') or '').upper().strip()
            date   = (p.get('date') or '').strip()
            if not ticker or not date:
                continue
            conn.execute(
                """
                INSERT INTO continuation_picks
                    (ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO NOTHING
                """,
                (
                    ticker,
                    date,
                    p.get('reason'),
                    p.get('gap_pct'),
                    p.get('float_shares'),
                    p.get('rvol_15m'),
                    p.get('sector'),
                    p.get('rank', 1),
                    now,
                )
            )
            inserted += 1

    return jsonify({'inserted': inserted}), 201


# ---------------------------------------------------------------------------
# Deactivate a pick (manual dismiss OR threshold breach)
# ---------------------------------------------------------------------------

@cont_picks_bp.route('/continuation-picks/<int:pick_id>/deactivate', methods=['POST'])
def deactivate_pick(pick_id: int):
    data   = request.get_json(silent=True) or {}
    reason = data.get('reason', 'manually dismissed')
    now    = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM continuation_picks WHERE id = %s", (pick_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        conn.execute(
            """
            UPDATE continuation_picks
            SET is_active = FALSE, deactivated_at = %s, deactivated_reason = %s
            WHERE id = %s
            """,
            (now, reason, pick_id)
        )
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Hard delete a pick
# ---------------------------------------------------------------------------

@cont_picks_bp.route('/continuation-picks/<int:pick_id>', methods=['DELETE'])
def delete_pick(pick_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM continuation_picks WHERE id = %s", (pick_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        conn.execute("DELETE FROM continuation_picks WHERE id = %s", (pick_id,))
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Stats endpoint — count active picks by date
# ---------------------------------------------------------------------------

@cont_picks_bp.route('/continuation-picks/stats', methods=['GET'])
def picks_stats():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date, COUNT(*) as count
            FROM continuation_picks
            WHERE is_active = TRUE
            GROUP BY date
            ORDER BY date DESC
            LIMIT 14
            """
        ).fetchall()
    return jsonify([dict(r) for r in rows])
