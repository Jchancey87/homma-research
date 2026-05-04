import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from database import get_connection

watchlist_bp = Blueprint('watchlist', __name__)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@watchlist_bp.route('/watchlist', methods=['GET'])
def list_watchlist():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist ORDER BY last_viewed_at DESC, added_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Add ticker
# ---------------------------------------------------------------------------

@watchlist_bp.route('/watchlist', methods=['POST'])
def add_to_watchlist():
    data   = request.get_json(silent=True) or {}
    ticker = (data.get('ticker') or '').upper().strip()
    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400

    sector   = (data.get('sector') or '').strip() or None
    notes    = (data.get('notes')  or '').strip() or None
    tags_raw = data.get('tags', [])
    if not isinstance(tags_raw, list):
        return jsonify({'error': 'tags must be a JSON array'}), 400
    tags = json.dumps([str(t).strip() for t in tags_raw if str(t).strip()])

    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO watchlist (ticker, sector, notes, tags, added_at) VALUES (?, ?, ?, ?, ?)",
                (ticker, sector, notes, tags, now),
            )
    except Exception as e:
        if 'UNIQUE' in str(e):
            return jsonify({'error': f'{ticker} is already on your watchlist'}), 409
        raise

    return jsonify({'ticker': ticker}), 201


# ---------------------------------------------------------------------------
# Update notes / tags / sector
# ---------------------------------------------------------------------------

@watchlist_bp.route('/watchlist/<ticker>', methods=['PUT'])
def update_watchlist_item(ticker):
    ticker = ticker.upper().strip()
    data   = request.get_json(silent=True) or {}

    allowed = {'notes', 'tags', 'sector'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if 'tags' in updates:
        if not isinstance(updates['tags'], list):
            return jsonify({'error': 'tags must be a list'}), 400
        updates['tags'] = json.dumps([str(t).strip() for t in updates['tags'] if str(t).strip()])

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values     = list(updates.values()) + [ticker]

    with get_connection() as conn:
        row = conn.execute("SELECT ticker FROM watchlist WHERE ticker = ?", (ticker,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        conn.execute(f"UPDATE watchlist SET {set_clause} WHERE ticker = ?", values)

    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Touch last_viewed_at (called when research page opens for a ticker)
# ---------------------------------------------------------------------------

@watchlist_bp.route('/watchlist/<ticker>/viewed', methods=['POST'])
def mark_viewed(ticker):
    ticker = ticker.upper().strip()
    now    = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE watchlist SET last_viewed_at = ? WHERE ticker = ?", (now, ticker)
        )
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Remove ticker
# ---------------------------------------------------------------------------

@watchlist_bp.route('/watchlist/<ticker>', methods=['DELETE'])
def remove_from_watchlist(ticker):
    ticker = ticker.upper().strip()
    with get_connection() as conn:
        row = conn.execute("SELECT ticker FROM watchlist WHERE ticker = ?", (ticker,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
    return jsonify({'success': True})
