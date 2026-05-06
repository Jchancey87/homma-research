import json
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from database import get_connection

observations_bp = Blueprint('observations', __name__)

VALID_SENTIMENTS = ('bullish', 'bearish', 'neutral')


# ---------------------------------------------------------------------------
# List / filter
# ---------------------------------------------------------------------------

@observations_bp.route('/observations', methods=['GET'])
def list_observations():
    ticker    = (request.args.get('ticker')    or '').upper().strip()
    sentiment = request.args.get('sentiment')
    tag       = request.args.get('tag')
    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')
    limit     = request.args.get('limit', 100, type=int)

    query  = "SELECT * FROM observations WHERE 1=1"
    params = []

    if ticker:
        query += " AND ticker = %s";    params.append(ticker)
    if sentiment:
        query += " AND sentiment = %s"; params.append(sentiment)
    if tag:
        # PostgreSQL LIKE is case-sensitive by default — use ILIKE or keep LIKE
        query += " AND tags ILIKE %s";  params.append(f'%{tag}%')
    if date_from:
        query += " AND date >= %s";     params.append(date_from)
    if date_to:
        query += " AND date <= %s";     params.append(date_to)

    query += " ORDER BY date DESC, created_at DESC LIMIT %s"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return jsonify([dict(r) for r in rows])


@observations_bp.route('/observations/<ticker>', methods=['GET'])
def get_observations_for_ticker(ticker):
    ticker = ticker.upper().strip()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM observations WHERE ticker = %s ORDER BY date DESC, created_at DESC",
            (ticker,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@observations_bp.route('/observations', methods=['POST'])
def create_observation():
    data = request.get_json(silent=True) or {}

    ticker    = (data.get('ticker') or '').upper().strip()
    date      = (data.get('date')   or '').strip()
    body      = (data.get('body')   or '').strip()
    title     = (data.get('title')  or '').strip() or None
    sentiment = (data.get('sentiment') or 'neutral').strip().lower()
    tags_raw  = data.get('tags', [])
    linked_chart_id = data.get('linked_chart_id')

    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400
    if not date:
        return jsonify({'error': 'date is required (YYYY-MM-DD)'}), 400
    if not body:
        return jsonify({'error': 'body is required'}), 400
    if sentiment not in VALID_SENTIMENTS:
        return jsonify({'error': f'sentiment must be one of {VALID_SENTIMENTS}'}), 400

    if not isinstance(tags_raw, list):
        return jsonify({'error': 'tags must be a JSON array'}), 400
    tags = json.dumps([str(t).strip() for t in tags_raw if str(t).strip()])

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO observations
               (ticker, date, title, body, sentiment, tags, linked_chart_id, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (ticker, date, title, body, sentiment, tags, linked_chart_id, now, now),
        )
        obs_id = cur.fetchone()['id']

    return jsonify({'id': obs_id}), 201


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@observations_bp.route('/observations/<int:obs_id>', methods=['PUT'])
def update_observation(obs_id):
    data = request.get_json(silent=True) or {}

    allowed = {'title', 'body', 'sentiment', 'tags', 'date', 'linked_chart_id'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if 'sentiment' in updates:
        if updates['sentiment'] not in VALID_SENTIMENTS:
            return jsonify({'error': f'sentiment must be one of {VALID_SENTIMENTS}'}), 400

    if 'tags' in updates:
        if not isinstance(updates['tags'], list):
            return jsonify({'error': 'tags must be a list'}), 400
        updates['tags'] = json.dumps([str(t).strip() for t in updates['tags'] if str(t).strip()])

    if 'body' in updates and not updates['body'].strip():
        return jsonify({'error': 'body cannot be empty'}), 400

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    updates['updated_at'] = datetime.now(timezone.utc).isoformat()
    set_clause = ', '.join(f'{k} = %s' for k in updates)
    values     = list(updates.values()) + [obs_id]

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM observations WHERE id = %s", (obs_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        conn.execute(f"UPDATE observations SET {set_clause} WHERE id = %s", values)

    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@observations_bp.route('/observations/<int:obs_id>', methods=['DELETE'])
def delete_observation(obs_id):
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM observations WHERE id = %s", (obs_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        conn.execute("DELETE FROM observations WHERE id = %s", (obs_id,))
    return jsonify({'success': True})
