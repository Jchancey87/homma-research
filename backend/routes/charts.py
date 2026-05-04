import json
import os
from flask import Blueprint, jsonify, request, send_from_directory
from database import get_connection
from services.chart_service import validate_tags, save_chart_image, VALID_TAGS
from config import Config

charts_bp = Blueprint('charts', __name__)


def _sync_chart_tags(conn, chart_id: int, tags: list):
    """Replace all chart_tags rows for chart_id with the new tag list."""
    conn.execute("DELETE FROM chart_tags WHERE chart_id = ?", (chart_id,))
    for tag in tags:
        tag = str(tag).strip()
        if tag:
            conn.execute(
                "INSERT OR IGNORE INTO chart_tags (chart_id, tag) VALUES (?, ?)",
                (chart_id, tag),
            )


@charts_bp.route('/charts', methods=['POST'])
def upload_chart():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided (field name: image)'}), 400

    file         = request.files['image']
    ticker       = (request.form.get('ticker') or '').upper().strip()
    capture_date = (request.form.get('capture_date') or '').strip()
    timeframe    = request.form.get('timeframe')
    setup_type   = request.form.get('setup_type')
    score        = request.form.get('cleanliness_score', type=int)
    notes        = request.form.get('notes', '')
    tags_raw     = request.form.get('tags', '[]')

    if not ticker or not capture_date:
        return jsonify({'error': 'ticker and capture_date are required'}), 400

    try:
        tags = json.loads(tags_raw)
        if not isinstance(tags, list):
            raise ValueError
    except Exception:
        return jsonify({'error': 'tags must be a JSON array'}), 400

    invalid = validate_tags(tags)
    if invalid:
        return jsonify({'error': f'Invalid tags: {invalid}', 'valid_tags': VALID_TAGS}), 422

    try:
        image_path = save_chart_image(file, ticker, capture_date)
    except ValueError as e:
        return jsonify({'error': str(e)}), 415

    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO chart_captures
               (ticker, capture_date, timeframe, image_path, setup_type,
                cleanliness_score, tags, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, capture_date, timeframe, image_path,
             setup_type, score, json.dumps(tags), notes),
        )
        chart_id = cur.lastrowid
        _sync_chart_tags(conn, chart_id, tags)

    return jsonify({'id': chart_id, 'image_path': image_path}), 201


@charts_bp.route('/charts', methods=['GET'])
def list_charts():
    ticker     = (request.args.get('ticker') or '').upper().strip()
    setup_type = request.args.get('setup_type')
    tag        = request.args.get('tag')
    date_from  = request.args.get('date_from')
    date_to    = request.args.get('date_to')
    min_clean  = request.args.get('min_cleanliness', type=int)

    query  = "SELECT DISTINCT cc.* FROM chart_captures cc"
    params = []

    if tag:
        query += " JOIN chart_tags ct ON ct.chart_id = cc.id AND ct.tag = ?"
        params.append(tag)

    query += " WHERE 1=1"

    if ticker:
        query += " AND cc.ticker = ?";     params.append(ticker)
    if setup_type:
        query += " AND cc.setup_type = ?"; params.append(setup_type)
    if date_from:
        query += " AND cc.capture_date >= ?"; params.append(date_from)
    if date_to:
        query += " AND cc.capture_date <= ?"; params.append(date_to)
    if min_clean is not None:
        query += " AND cc.cleanliness_score >= ?"; params.append(min_clean)

    query += " ORDER BY cc.capture_date DESC, cc.created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return jsonify([dict(r) for r in rows])


@charts_bp.route('/charts/<int:chart_id>', methods=['GET'])
def get_chart(chart_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM chart_captures WHERE id = ?", (chart_id,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))


@charts_bp.route('/charts/<int:chart_id>', methods=['PUT'])
def update_chart(chart_id):
    data    = request.get_json(silent=True) or {}
    allowed = {'notes', 'tags', 'cleanliness_score', 'setup_type', 'timeframe'}
    updates = {k: v for k, v in data.items() if k in allowed}

    if 'tags' in updates:
        tags = updates['tags']
        if not isinstance(tags, list):
            return jsonify({'error': 'tags must be a list'}), 400
        invalid = validate_tags(tags)
        if invalid:
            return jsonify({'error': f'Invalid tags: {invalid}', 'valid_tags': VALID_TAGS}), 422
        updates['tags'] = json.dumps(tags)

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    tag_list = None
    if 'tags' in updates:
        # Already validated above; decode for junction table sync
        tag_list = json.loads(updates['tags'])

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values     = list(updates.values()) + [chart_id]

    with get_connection() as conn:
        conn.execute(f"UPDATE chart_captures SET {set_clause} WHERE id = ?", values)
        if tag_list is not None:
            _sync_chart_tags(conn, chart_id, tag_list)

    return jsonify({'success': True})


@charts_bp.route('/charts/<int:chart_id>', methods=['DELETE'])
def delete_chart(chart_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT image_path, gemini_image_path FROM chart_captures WHERE id = ?",
            (chart_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404

        for path_field in ('image_path', 'gemini_image_path'):
            p = row[path_field]
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

        # chart_tags rows deleted by CASCADE
        conn.execute("DELETE FROM chart_captures WHERE id = ?", (chart_id,))

    return jsonify({'success': True})


@charts_bp.route('/charts/<int:chart_id>/gemini-import', methods=['POST'])
def gemini_import(chart_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT ticker, capture_date FROM chart_captures WHERE id = ?",
            (chart_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404

        ticker = row['ticker']
        capture_date = row['capture_date']

    if request.is_json:
        data = request.get_json() or {}
        analysis_text = data.get('analysis_text', '').strip()
        image_file = None
    else:
        analysis_text = request.form.get('analysis_text', '').strip()
        image_file = request.files.get('annotated_image') or request.files.get('image')

    image_path = None
    if image_file:
        try:
            image_path = save_chart_image(
                image_file, 
                ticker=ticker, 
                capture_date=capture_date,
                subfolder='annotated'
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 415

    with get_connection() as conn:
        if image_path:
            conn.execute(
                """UPDATE chart_captures 
                   SET gemini_annotation = ?, 
                       llm_annotation = ?, 
                       gemini_image_path = ?,
                       gemini_imported_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (analysis_text, analysis_text, image_path, chart_id)
            )
        else:
            conn.execute(
                """UPDATE chart_captures 
                   SET gemini_annotation = ?, 
                       llm_annotation = ?,
                       gemini_imported_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (analysis_text, analysis_text, chart_id)
            )

    return jsonify({
        'success': True,
        'gemini_image_path': image_path,
        'analysis_text': analysis_text
    })
