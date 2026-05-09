import io
import csv
from flask import Blueprint, jsonify, request, Response
from services.gainer_service import get_gainers_filtered, get_sectors
from services.heatmap_service import build_heatmap_spec
from services.archetype_service import get_archetype_stats

gainers_bp = Blueprint('gainers', __name__)


@gainers_bp.route('/gainers/live', methods=['GET'])
def live_gainers():
    """
    Real-time top-10 gainer screener powered by the Polygon Snapshot API.
    Results are cached in-memory for CACHE_TTL_SECONDS (default 5 min).
    Pass ?force=1 to bypass cache and re-fetch immediately.
    """
    force = request.args.get('force', '').strip() in ('1', 'true', 'yes')
    try:
        from services.live_screener import get_live_gainers, refresh_cache
        if force:
            refresh_cache(force=True)
        return jsonify(get_live_gainers())
    except Exception as e:
        return jsonify({'error': str(e)}), 500



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

    period      = (request.args.get('period') or 'all').lower()
    view        = (request.args.get('view')   or 'float_rvol').lower()
    exact_date  = request.args.get('date')
    min_gap     = request.args.get('min_gap',   type=float)
    max_float_m = request.args.get('max_float', type=float)
    min_rvol    = request.args.get('min_rvol',  type=float)
    sector      = request.args.get('sector')

    cutoff = None
    if not exact_date:
        today  = datetime.utcnow().date()
        if period == 'week':
            cutoff = (today - timedelta(days=7)).isoformat()
        elif period == 'month':
            cutoff = (today - timedelta(days=30)).isoformat()
        elif period == 'year':
            cutoff = (today - timedelta(days=365)).isoformat()

    if view == 'sector':
        return jsonify(get_sector_spec(
            cutoff_date=cutoff, exact_date=exact_date, min_gap=min_gap,
            max_float_m=max_float_m, min_rvol=min_rvol, sector=sector
        ))
    return jsonify(build_heatmap_spec(
        cutoff_date=cutoff, exact_date=exact_date, min_gap=min_gap,
        max_float_m=max_float_m, min_rvol=min_rvol, sector=sector
    ))


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
    """Dashboard endpoint: latest ingest date + top 9 gainers for that date + total count."""
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
               FROM daily_gainers WHERE date = %s
               ORDER BY gap_pct DESC LIMIT 9""",
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


@gainers_bp.route('/gainers/pipe-scan', methods=['GET'])
def pipe_scan():
    """
    Batch-scan all gainers for a given date for PIPE/private placement activity.
    Results are cached in pipe_filings table; only hits EDGAR for new scans.

    Query params:
      date — YYYY-MM-DD (required)
    """
    date = (request.args.get('date') or '').strip()
    if not date:
        return jsonify({'error': 'date is required'}), 400

    try:
        from services.pipe_service import batch_scan_gainers
        results = batch_scan_gainers(date)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

    period      = (request.args.get('period') or 'all').lower()
    search      = (request.args.get('search') or '').upper().strip()
    sort        = (request.args.get('sort')   or 'last_seen').lower()
    limit       = request.args.get('limit', 500, type=int)
    exact_date  = request.args.get('date')
    min_gap     = request.args.get('min_gap',   type=float)
    max_float_m = request.args.get('max_float', type=float)
    min_rvol    = request.args.get('min_rvol',  type=float)
    sector      = request.args.get('sector')
    min_price   = request.args.get('min_price', type=float)
    max_price   = request.args.get('max_price', type=float)

    # Period cutoff - Ignored if searching for a specific ticker
    cutoff = None
    if not exact_date and not search:
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
    if exact_date:
        conditions.append('date = %s')
        params.append(exact_date)
    elif cutoff:
        conditions.append('date >= %s')
        params.append(cutoff)
    
    if search:
        conditions.append('ticker LIKE %s')
        params.append(f'{search}%')
    if min_gap:
        conditions.append('gap_pct >= %s')
        params.append(min_gap)
    if max_float_m:
        conditions.append('float_shares <= %s')
        params.append(max_float_m * 1_000_000)
    if min_rvol:
        conditions.append('rvol_15m >= %s')
        params.append(min_rvol)
    if sector:
        conditions.append('sector = %s')
        params.append(sector)
    if min_price:
        conditions.append('close_price >= %s')
        params.append(min_price)
    if max_price:
        conditions.append('close_price <= %s')
        params.append(max_price)

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
                ROUND(AVG(gap_pct)::numeric,  2)::float             AS avg_gap_pct,
                ROUND(AVG(rvol_15m)::numeric, 2)::float             AS avg_rvol,
                ROUND((AVG(float_shares) / 1e6)::numeric, 2)::float AS avg_float_m,
                MAX(gap_pct)::float                                  AS max_gap_pct,
                MAX(close_price)::float                              AS last_close,
                MAX(market_cap)::float                               AS last_market_cap
            FROM daily_gainers
            {where}
            GROUP BY ticker
            ORDER BY {order_clause}
            LIMIT %s
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
        sql    = "SELECT * FROM daily_gainers WHERE ticker = %s AND date >= %s ORDER BY date DESC"
        params = (ticker, cutoff)
    else:
        sql    = "SELECT * FROM daily_gainers WHERE ticker = %s ORDER BY date DESC"
        params = (ticker,)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return jsonify([dict(r) for r in rows])


# ── New Dashboard Intelligence Endpoints ─────────────────────────────────────

@gainers_bp.route('/gainers/repeat-runners', methods=['GET'])
def repeat_runners():
    """
    Cross-reference today's live snapshot tickers against historical ingest.
    Returns tickers that are moving today AND have appeared in the DB before,
    giving traders instant context: 'MOBI ran before — here's its history.'
    """
    from database import get_connection
    try:
        from services.live_screener import get_live_gainers
        snapshot = get_live_gainers()
        today_tickers = [g['ticker'] for g in snapshot.get('gainers', [])]
    except Exception:
        return jsonify([])

    if not today_tickers:
        return jsonify([])

    placeholders = ', '.join(['%s'] * len(today_tickers))
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT
                ticker,
                COUNT(*)                                           AS appearances,
                ROUND(AVG(gap_pct)::numeric, 1)::float             AS avg_gap_pct,
                MAX(gap_pct)::float                                AS best_gap_pct,
                MAX(date)                                          AS last_seen,
                MIN(date)                                          AS first_seen,
                ROUND(AVG(rvol_15m)::numeric, 1)::float           AS avg_rvol,
                ROUND((AVG(float_shares)/1e6)::numeric, 1)::float AS avg_float_m
            FROM daily_gainers
            WHERE ticker IN ({placeholders})
            GROUP BY ticker
            ORDER BY appearances DESC, best_gap_pct DESC
        """, today_tickers).fetchall()

    return jsonify([dict(r) for r in rows])


@gainers_bp.route('/gainers/float-buckets', methods=['GET'])
def float_buckets():
    """
    Bucket today's (or a given date's) gainers by float tier.
    Helps identify which float category is 'in play' on a given day.
    Tiers: Nano (<10M), Micro (10-50M), Small (50-200M), Mid (>200M)
    """
    from database import get_connection
    from datetime import datetime
    exact_date = request.args.get('date') or datetime.utcnow().strftime('%Y-%m-%d')

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                CASE
                    WHEN float_shares < 10e6   THEN 'Nano'
                    WHEN float_shares < 50e6   THEN 'Micro'
                    WHEN float_shares < 200e6  THEN 'Small'
                    ELSE                            'Mid+'
                END                                                AS bucket,
                COUNT(*)                                           AS count,
                ROUND(AVG(gap_pct)::numeric, 1)::float             AS avg_gap_pct,
                MAX(gap_pct)::float                                AS best_gap_pct
            FROM daily_gainers
            WHERE date = %s AND float_shares IS NOT NULL
            GROUP BY bucket
            ORDER BY avg_gap_pct DESC NULLS LAST
        """, (exact_date,)).fetchall()

    return jsonify({'date': exact_date, 'buckets': [dict(r) for r in rows]})


@gainers_bp.route('/gainers/follow-through', methods=['GET'])
def follow_through():
    """
    Checks if yesterday's top gainers are following through today.
    Compares yesterday's close to today's Polygon live price.
    """
    from database import get_connection
    from datetime import datetime, timedelta
    import requests as _req
    from config import Config

    today     = datetime.utcnow().date()
    yesterday = (today - timedelta(days=1)).isoformat()

    with get_connection() as conn:
        # Walk back up to 5 days to find the last trading day with data
        rows = None
        for offset in range(1, 8):
            check_date = (today - timedelta(days=offset)).isoformat()
            rows = conn.execute("""
                SELECT ticker, gap_pct, close_price, float_shares
                FROM daily_gainers
                WHERE date = %s
                ORDER BY gap_pct DESC NULLS LAST
                LIMIT 5
            """, (check_date,)).fetchall()
            if rows:
                yesterday = check_date
                break

    if not rows:
        return jsonify({'date': yesterday, 'results': []})

    tickers = [r['ticker'] for r in rows]
    prev_closes = {r['ticker']: r['close_price'] for r in rows}
    prev_gaps   = {r['ticker']: r['gap_pct'] for r in rows}

    # Fetch live prices from Polygon
    live_prices = {}
    polygon_key = getattr(Config, 'POLYGON_API_KEY', None)
    if polygon_key:
        try:
            for ticker in tickers:
                url = f'https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}'
                resp = _req.get(url, params={'apiKey': polygon_key}, timeout=5)
                if resp.ok:
                    data = resp.json()
                    day = data.get('ticker', {}).get('day', {})
                    live_prices[ticker] = day.get('o') or day.get('c')
        except Exception:
            pass

    results = []
    for ticker in tickers:
        prev_close  = prev_closes.get(ticker)
        live_price  = live_prices.get(ticker)
        change_pct  = None
        status      = 'no_data'

        if prev_close and live_price:
            change_pct = round((live_price - prev_close) / prev_close * 100, 1)
            if change_pct >= 2:
                status = 'following'
            elif change_pct <= -2:
                status = 'fading'
            else:
                status = 'flat'

        results.append({
            'ticker':      ticker,
            'prev_date':   yesterday,
            'prev_gap':    prev_gaps.get(ticker),
            'prev_close':  prev_close,
            'today_open':  live_price,
            'change_pct':  change_pct,
            'status':      status,
        })

    return jsonify({'date': yesterday, 'results': results})


@gainers_bp.route('/gainers/sector-rotation', methods=['GET'])
def sector_rotation():
    """
    Compare this week's vs last week's top sectors by average gap %.
    Surfaces which sectors are gaining / losing momentum.
    """
    from database import get_connection
    from datetime import datetime, timedelta

    today      = datetime.utcnow().date()
    this_week  = (today - timedelta(days=7)).isoformat()
    last_week  = (today - timedelta(days=14)).isoformat()

    with get_connection() as conn:
        this_rows = conn.execute("""
            SELECT sector,
                   COUNT(*)                                    AS count,
                   ROUND(AVG(gap_pct)::numeric, 1)::float      AS avg_gap_pct
            FROM daily_gainers
            WHERE date >= %s AND sector IS NOT NULL AND sector != ''
            GROUP BY sector
            ORDER BY avg_gap_pct DESC NULLS LAST
            LIMIT 6
        """, (this_week,)).fetchall()

        last_rows = conn.execute("""
            SELECT sector,
                   ROUND(AVG(gap_pct)::numeric, 1)::float      AS avg_gap_pct
            FROM daily_gainers
            WHERE date >= %s AND date < %s AND sector IS NOT NULL AND sector != ''
            GROUP BY sector
            ORDER BY avg_gap_pct DESC NULLS LAST
            LIMIT 6
        """, (last_week, this_week)).fetchall()

    last_map = {r['sector']: r['avg_gap_pct'] for r in last_rows}
    last_sectors = [r['sector'] for r in last_rows]

    result = []
    for i, r in enumerate(this_rows):
        sector = r['sector']
        last_avg = last_map.get(sector)
        last_rank = last_sectors.index(sector) + 1 if sector in last_sectors else None
        trend = 'new'
        if last_avg is not None:
            diff = (r['avg_gap_pct'] or 0) - (last_avg or 0)
            trend = 'up' if diff >= 2 else 'down' if diff <= -2 else 'flat'

        result.append({
            'sector':       sector,
            'count':        r['count'],
            'avg_gap_pct':  r['avg_gap_pct'],
            'last_avg_gap': last_avg,
            'last_rank':    last_rank,
            'this_rank':    i + 1,
            'trend':        trend,
        })

    return jsonify(result)

