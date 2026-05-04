import io
import csv
from flask import Blueprint, jsonify, request, Response
from services.gainer_service import get_gainers_filtered, get_sectors
from services.heatmap_service import build_heatmap_spec
from services.archetype_service import get_archetype_stats

gainers_bp = Blueprint('gainers', __name__)


@gainers_bp.route('/gainers', methods=['GET'])
def list_gainers():
    gainers = get_gainers_filtered(
        date        = request.args.get('date'),
        min_gap     = request.args.get('min_gap',   type=float),
        max_float_m = request.args.get('max_float', type=float),
        min_rvol    = request.args.get('min_rvol',  type=float),
        sector      = request.args.get('sector'),
    )
    return jsonify(gainers)


@gainers_bp.route('/gainers/heatmap', methods=['GET'])
def heatmap():
    from datetime import datetime, timedelta
    from services.heatmap_service import get_sector_spec

    period = (request.args.get('period') or 'all').lower()
    view   = (request.args.get('view')   or 'float_rvol').lower()

    cutoff = None
    today  = datetime.utcnow().date()
    if period == 'week':
        cutoff = (today - timedelta(days=7)).isoformat()
    elif period == 'month':
        cutoff = (today - timedelta(days=30)).isoformat()
    elif period == 'year':
        cutoff = (today - timedelta(days=365)).isoformat()

    if view == 'sector':
        return jsonify(get_sector_spec(cutoff_date=cutoff))
    return jsonify(build_heatmap_spec(cutoff_date=cutoff))


@gainers_bp.route('/gainers/export', methods=['GET'])
def export_gainers():
    """CSV export — honours the same filter params as /gainers."""
    gainers = get_gainers_filtered(
        date        = request.args.get('date'),
        min_gap     = request.args.get('min_gap',   type=float),
        max_float_m = request.args.get('max_float', type=float),
        min_rvol    = request.args.get('min_rvol',  type=float),
        sector      = request.args.get('sector'),
    )

    if not gainers:
        return Response('', mimetype='text/csv')

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=gainers[0].keys())
    writer.writeheader()
    writer.writerows(gainers)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=gainers.csv'},
    )


@gainers_bp.route('/gainers/sectors', methods=['GET'])
def sectors():
    return jsonify(get_sectors())


@gainers_bp.route('/gainers/summary', methods=['GET'])
def gainers_summary():
    """Dashboard endpoint: latest ingest date + top 10 gainers for that date + total count."""
    from database import get_connection
    with get_connection() as conn:
        date_row = conn.execute(
            "SELECT date, COUNT(*) as total FROM daily_gainers "
            "GROUP BY date ORDER BY date DESC LIMIT 1"
        ).fetchone()

        if not date_row:
            return jsonify({'date': None, 'total': 0, 'gainers': []})

        latest_date = date_row['date']
        total       = date_row['total']

        rows = conn.execute(
            """SELECT ticker, gap_pct, float_shares, rvol_15m, sector,
                      news_headline, news_fresh, close_price, open_price
               FROM daily_gainers WHERE date = ?
               ORDER BY gap_pct DESC LIMIT 10""",
            (latest_date,),
        ).fetchall()

    return jsonify({
        'date':    latest_date,
        'total':   total,
        'gainers': [dict(r) for r in rows],
    })


@gainers_bp.route('/archetypes', methods=['GET'])
def archetypes():
    return jsonify(get_archetype_stats())


@gainers_bp.route('/gainers/ticker-history', methods=['GET'])
def ticker_history():
    """
    Aggregated per-ticker appearance history.

    Query params:
      period   — week | month | year | all  (default: all)
      search   — partial ticker symbol match
      sort     — appearances | last_seen | avg_gap  (default: last_seen)
      limit    — max tickers to return (default: 200)
    """
    from database import get_connection
    from datetime import datetime, timedelta

    period = (request.args.get('period') or 'all').lower()
    search = (request.args.get('search') or '').upper().strip()
    sort   = (request.args.get('sort')   or 'last_seen').lower()
    limit  = request.args.get('limit', 200, type=int)

    # Period cutoff
    cutoff = None
    today  = datetime.utcnow().date()
    if period == 'week':
        cutoff = (today - timedelta(days=7)).isoformat()
    elif period == 'month':
        cutoff = (today - timedelta(days=30)).isoformat()
    elif period == 'year':
        cutoff = (today - timedelta(days=365)).isoformat()

    # Build query
    conditions = []
    params     = []
    if cutoff:
        conditions.append('date >= ?')
        params.append(cutoff)
    if search:
        conditions.append('ticker LIKE ?')
        params.append(f'{search}%')

    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

    order_map = {
        'appearances': 'appearances DESC',
        'avg_gap':     'avg_gap_pct DESC',
        'last_seen':   'last_seen DESC',
        'first_seen':  'first_seen ASC',
    }
    order_clause = order_map.get(sort, 'last_seen DESC')

    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT
                ticker,
                MAX(sector)                         AS sector,
                COUNT(*)                            AS appearances,
                MAX(date)                           AS last_seen,
                MIN(date)                           AS first_seen,
                ROUND(AVG(gap_pct),  2)             AS avg_gap_pct,
                ROUND(AVG(rvol_15m), 2)             AS avg_rvol,
                ROUND(AVG(float_shares) / 1e6, 2)  AS avg_float_m,
                MAX(gap_pct)                        AS max_gap_pct
            FROM daily_gainers
            {where}
            GROUP BY ticker
            ORDER BY {order_clause}
            LIMIT ?
        """, params).fetchall()

    return jsonify([dict(r) for r in rows])


@gainers_bp.route('/gainers/ticker/<ticker>', methods=['GET'])
def ticker_appearances(ticker):
    """
    All individual daily_gainers rows for a specific ticker, newest first.
    Optionally bounded by ?period=week|month|year.
    """
    from database import get_connection
    from datetime import datetime, timedelta

    ticker = ticker.upper().strip()
    period = (request.args.get('period') or 'all').lower()

    cutoff = None
    today  = datetime.utcnow().date()
    if period == 'week':
        cutoff = (today - timedelta(days=7)).isoformat()
    elif period == 'month':
        cutoff = (today - timedelta(days=30)).isoformat()
    elif period == 'year':
        cutoff = (today - timedelta(days=365)).isoformat()

    if cutoff:
        sql    = "SELECT * FROM daily_gainers WHERE ticker = ? AND date >= ? ORDER BY date DESC"
        params = (ticker, cutoff)
    else:
        sql    = "SELECT * FROM daily_gainers WHERE ticker = ? ORDER BY date DESC"
        params = (ticker,)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return jsonify([dict(r) for r in rows])
