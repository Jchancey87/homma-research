import uuid
import threading
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from database import get_connection
from services.chart_service import save_chart_image

analysis_bp = Blueprint('analysis', __name__)


# ---------------------------------------------------------------------------
# Gemini import
# ---------------------------------------------------------------------------

@analysis_bp.route('/charts/<int:chart_id>/gemini-import', methods=['POST'])
def gemini_import(chart_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM chart_captures WHERE id = %s", (chart_id,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'Chart not found'}), 404

    # Support both JSON body and multipart form
    if request.content_type and 'application/json' in request.content_type:
        data          = request.get_json(silent=True) or {}
        analysis_text = data.get('analysis_text', '').strip()
    else:
        analysis_text = (request.form.get('analysis_text') or '').strip()

    if not analysis_text:
        return jsonify({'error': 'analysis_text is required and cannot be empty'}), 400

    gemini_image_path = None
    if 'annotated_image' in request.files:
        try:
            gemini_image_path = save_chart_image(
                request.files['annotated_image'],
                subfolder='annotated',
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 415

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        if gemini_image_path:
            conn.execute(
                """UPDATE chart_captures
                   SET gemini_annotation = %s, gemini_image_path = %s, gemini_imported_at = %s
                   WHERE id = %s""",
                (analysis_text, gemini_image_path, now, chart_id),
            )
        else:
            conn.execute(
                """UPDATE chart_captures
                   SET gemini_annotation = %s, gemini_imported_at = %s
                   WHERE id = %s""",
                (analysis_text, now, chart_id),
            )

    return jsonify({'success': True, 'imported_at': now})


# ---------------------------------------------------------------------------
# LLM jobs — continuation & sentiment
# ---------------------------------------------------------------------------

@analysis_bp.route('/continuation', methods=['POST'])
def start_continuation():
    data = request.get_json(silent=True) or {}
    date = (data.get('date') or '').strip()
    if not date:
        return jsonify({'error': 'date is required (YYYY-MM-DD)'}), 400

    job_id = str(uuid.uuid4())
    _create_job(job_id, 'continuation', date)
    threading.Thread(target=_run_continuation, args=(job_id, date), daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'pending'})


@analysis_bp.route('/sentiment', methods=['POST'])
def start_sentiment():
    data  = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'error': 'query is required'}), 400

    job_id = str(uuid.uuid4())
    _create_job(job_id, 'sentiment', query[:200])
    threading.Thread(target=_run_sentiment, args=(job_id, query), daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'pending'})


@analysis_bp.route('/research', methods=['POST'])
def start_research():
    data   = request.get_json(silent=True) or {}
    ticker = (data.get('ticker') or '').strip().upper()
    date   = (data.get('date') or '').strip()
    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400

    job_id = str(uuid.uuid4())
    _create_job(job_id, 'research', ticker)
    base_url = request.host_url.rstrip('/')
    threading.Thread(target=_run_deep_research, args=(job_id, ticker, date, base_url), daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'pending'})


@analysis_bp.route('/research/risk', methods=['POST'])
def start_risk_detection():
    data   = request.get_json(silent=True) or {}
    ticker = (data.get('ticker') or '').strip().upper()
    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400

    job_id = str(uuid.uuid4())
    _create_job(job_id, 'risk_detection', ticker)
    threading.Thread(target=_run_risk_detection, args=(job_id, ticker), daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'pending'})


@analysis_bp.route('/research/catalyst', methods=['POST'])
def start_catalyst_analysis():
    data   = request.get_json(silent=True) or {}
    ticker = (data.get('ticker') or '').strip().upper()
    date   = (data.get('date') or '').strip()
    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400

    job_id = str(uuid.uuid4())
    _create_job(job_id, 'catalyst_analysis', ticker)
    threading.Thread(target=_run_catalyst_analysis, args=(job_id, ticker, date), daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'pending'})


@analysis_bp.route('/research/context', methods=['POST'])
def start_deep_context():
    data   = request.get_json(silent=True) or {}
    ticker = (data.get('ticker') or '').strip().upper()
    if not ticker:
        return jsonify({'error': 'ticker is required'}), 400

    job_id = str(uuid.uuid4())
    _create_job(job_id, 'deep_context', ticker)
    threading.Thread(target=_run_deep_context, args=(job_id, ticker), daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'pending'})


@analysis_bp.route('/jobs/<job_id>/retry', methods=['POST'])
def retry_job(job_id):
    """Re-fire a job that is in 'error' status or stale 'running' status."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM llm_jobs WHERE id = %s", (job_id,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'Job not found'}), 404

    job = dict(row)
    if job['status'] not in ('error', 'running'):
        return jsonify({'error': f"Cannot retry a job with status '{job['status']}'"}), 400

    jtype     = job['type']
    input_ref = job.get('input_ref', '')

    # Reset the existing job to pending so the frontend can poll it
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE llm_jobs SET status='pending', output=NULL, updated_at=%s WHERE id=%s",
            (now, job_id),
        )

    base_url = request.host_url.rstrip('/')

    if jtype == 'continuation':
        threading.Thread(target=_run_continuation, args=(job_id, input_ref), daemon=True).start()
    elif jtype == 'sentiment':
        threading.Thread(target=_run_sentiment, args=(job_id, input_ref), daemon=True).start()
    elif jtype == 'research':
        threading.Thread(target=_run_deep_research, args=(job_id, input_ref, '', base_url), daemon=True).start()
    elif jtype == 'risk_detection':
        threading.Thread(target=_run_risk_detection, args=(job_id, input_ref), daemon=True).start()
    elif jtype == 'catalyst_analysis':
        threading.Thread(target=_run_catalyst_analysis, args=(job_id, input_ref, ''), daemon=True).start()
    elif jtype == 'deep_context':
        threading.Thread(target=_run_deep_context, args=(job_id, input_ref), daemon=True).start()
    else:
        return jsonify({'error': f"Unknown job type '{jtype}' — cannot retry"}), 400

    return jsonify({'job_id': job_id, 'status': 'pending'})



@analysis_bp.route('/research/chart-data', methods=['GET'])
def get_chart_data():
    """Return OHLCV + all indicator series as JSON for the interactive Lightweight Charts frontend."""
    import pandas as pd
    import numpy as np

    ticker = (request.args.get('ticker') or '').strip().upper()
    date   = (request.args.get('date')   or '').strip()
    if not ticker or not date:
        return jsonify({'error': 'ticker and date are required'}), 400

    # 1. Fetch intraday bars (Polygon primary, yfinance fallback)
    bars_df = _fetch_intraday_polygon(ticker, date)

    if bars_df.empty:
        # yfinance fallback
        try:
            import yfinance as yf
            from datetime import timedelta
            start_dt = datetime.strptime(date, '%Y-%m-%d')
            end_dt   = start_dt + timedelta(days=1)
            yf_df = yf.download(ticker,
                                 start=start_dt.strftime('%Y-%m-%d'),
                                 end=end_dt.strftime('%Y-%m-%d'),
                                 interval='1m', prepost=True, progress=False)
            if not yf_df.empty:
                if hasattr(yf_df.columns, 'levels'):
                    yf_df.columns = yf_df.columns.get_level_values(0)
                yf_df = yf_df.rename(columns={
                    'Open': 'open', 'High': 'high', 'Low': 'low',
                    'Close': 'close', 'Volume': 'volume'
                })
                bars_df = yf_df
        except Exception as e:
            print(f"yfinance fallback failed in chart-data: {e}")

    if bars_df.empty:
        return jsonify({'error': f'No intraday data available for {ticker} on {date}'}), 404

    df = bars_df[['open', 'high', 'low', 'close', 'volume']].copy()

    # 2. Convert index to Unix seconds (lightweight-charts requires integer seconds).
    # Use pd.Timestamp epoch subtraction which is resolution-safe: works whether the
    # DatetimeIndex has dtype datetime64[s], datetime64[ms], or datetime64[ns, UTC].
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_convert('UTC')
    else:
        df.index = df.index.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
    epoch = pd.Timestamp('1970-01-01', tz='UTC')
    df['time'] = ((df.index - epoch).total_seconds()).astype(int)

    # 3. Calculate EMA Ribbon
    for span in [8, 13, 21, 34, 55]:
        df[f'ema_{span}'] = df['close'].ewm(span=span, adjust=False).mean()

    # 4. RVOL
    vol_avg = df['volume'].rolling(20).mean()
    df['rvol'] = (df['volume'] / vol_avg).fillna(1.0)

    # 5. ATR
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift(1)).abs()
    tr3 = (df['low']  - df['close'].shift(1)).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()

    # 6. ADX / +DI / -DI
    up_move   = df['high'] - df['high'].shift(1)
    down_move = df['low'].shift(1) - df['low']
    pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    pos_dm_s  = pd.Series(pos_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean()
    neg_dm_s  = pd.Series(neg_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean()
    tr_s      = tr.ewm(alpha=1/14, adjust=False).mean()
    df['plus_di']  = 100 * (pos_dm_s / tr_s)
    df['minus_di'] = 100 * (neg_dm_s / tr_s)
    dx = 100 * (df['plus_di'] - df['minus_di']).abs() / (df['plus_di'] + df['minus_di']).abs()
    df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()

    # 7. Volume colours
    vol_colors = ['rgba(34,211,167,0.5)' if c >= o else 'rgba(240,77,90,0.5)'
                  for c, o in zip(df['close'], df['open'])]

    # 8. Drop NaNs and build JSON series
    df = df.dropna(subset=['ema_55', 'adx'])
    t = df['time'].tolist()

    def line_series(col: str):
        return [{'time': int(ti), 'value': round(float(v), 4)}
                for ti, v in zip(t, df[col]) if not (isinstance(v, float) and v != v)]

    ohlcv_records = [
        {'time': int(ti), 'open': round(float(o), 4), 'high': round(float(h), 4),
         'low': round(float(l), 4), 'close': round(float(c), 4)}
        for ti, o, h, l, c in zip(t, df['open'], df['high'], df['low'], df['close'])
    ]
    vol_records = [
        {'time': int(ti), 'value': int(v), 'color': col}
        for ti, v, col in zip(t, df['volume'], vol_colors)
    ]

    return jsonify({
        'ohlcv':    ohlcv_records,
        'volume':   vol_records,
        'rvol':     line_series('rvol'),
        'ema_8':    line_series('ema_8'),
        'ema_13':   line_series('ema_13'),
        'ema_21':   line_series('ema_21'),
        'ema_34':   line_series('ema_34'),
        'ema_55':   line_series('ema_55'),
        'adx':      line_series('adx'),
        'plus_di':  line_series('plus_di'),
        'minus_di': line_series('minus_di'),
        'atr':      line_series('atr'),
    })


@analysis_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """List past LLM jobs, newest first. Optional ?type=continuation filter."""
    jtype  = request.args.get('type')
    limit  = request.args.get('limit', 50, type=int)
    query  = "SELECT * FROM llm_jobs WHERE 1=1"
    params = []
    if jtype:
        query += " AND type = %s"; params.append(jtype)
    query += " ORDER BY created_at DESC LIMIT %s"; params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@analysis_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM llm_jobs WHERE id = %s", (job_id,)
        ).fetchone()
    if not row:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(dict(row))


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------

def _run_continuation(job_id: str, date: str):
    _set_status(job_id, 'running')
    try:
        with get_connection() as conn:
            # Top 10 gainers for the requested date
            gainer_rows = conn.execute(
                """SELECT ticker, gap_pct, float_shares, rvol_15m, sector,
                          news_headline, news_fresh, close_price, open_price
                   FROM daily_gainers WHERE date = %s
                   ORDER BY gap_pct DESC LIMIT 10""",
                (date,),
            ).fetchall()

            # Historical archetype stats to ground the report
            archetype_rows = conn.execute(
                """SELECT tags as tag,
                          COUNT(*) as count,
                          ROUND(AVG(gap_pct), 1) as avg_gap_pct,
                          ROUND(AVG(rvol_15m), 1) as avg_rvol,
                          ROUND(AVG(cleanliness_score), 1) as avg_cleanliness
                   FROM chart_captures
                   WHERE tags IS NOT NULL AND tags != '[]'
                   GROUP BY tags
                   ORDER BY count DESC"""
            ).fetchall()

        if not gainer_rows:
            _set_status(job_id, 'error', output=f'No gainers found in the database for {date}. '
                        'Run the ingestion job or try a different date.')
            return

        from llm.llm_client import get_continuation_analysis
        from services.archetype_service import get_archetype_stats

        gainers        = [dict(r) for r in gainer_rows]
        archetype_stats = get_archetype_stats()  # full enriched stats

        output, model = get_continuation_analysis(date, gainers, archetype_stats)
        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        _set_status(job_id, 'error', output=str(e))


def _run_sentiment(job_id: str, query: str):
    _set_status(job_id, 'running')
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT tags, AVG(cleanliness_score) as avg_cleanliness, COUNT(*) as count
                   FROM chart_captures
                   WHERE tags IS NOT NULL AND tags != '[]'
                   GROUP BY tags"""
            ).fetchall()

        from llm.llm_client import get_sentiment_analysis
        output, model = get_sentiment_analysis(query, [dict(r) for r in rows])
        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        _set_status(job_id, 'error', output=str(e))


def _fetch_intraday_polygon(ticker: str, date: str):
    import requests
    import pandas as pd
    from config import Config
    
    api_key = Config.POLYGON_API_KEY
    if not api_key:
        print("Warning: POLYGON_API_KEY not set. Skipping intraday fetch.")
        return pd.DataFrame()
        
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{date}/{date}"
    params = {
        'adjusted': 'true',
        'sort': 'asc',
        'limit': 50000,
        'apiKey': api_key
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if 'results' not in data or not data['results']:
            return pd.DataFrame()
            
        df = pd.DataFrame(data['results'])
        # Rename columns to match standard ohlcv
        df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 'vw': 'vwap', 't': 'timestamp'})
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        # Assuming US/Eastern for display purposes
        df['timestamp'] = df['timestamp'].dt.tz_convert('America/New_York')
        df = df.set_index('timestamp')
        return df
    except Exception as e:
        print(f"Error fetching polygon data: {e}")
        return pd.DataFrame()

def _run_deep_research(job_id: str, ticker: str, date: str, base_url: str):
    import yfinance as yf
    _set_status(job_id, 'running')
    try:
        # ── 1. Fundamentals: FMP primary, yfinance fallback ──────────────────
        from services.fmp_service import (
            get_company_profile,
            get_analyst_estimates,
            get_income_statement,
            get_key_metrics,
            get_earnings_calendar as fmp_earnings,
        )
        import pytz

        profile    = get_company_profile(ticker)
        estimates  = get_analyst_estimates(ticker)
        income     = get_income_statement(ticker)
        key_m      = get_key_metrics(ticker)
        earnings   = fmp_earnings(ticker)

        # yfinance still used for: news, actions, options (not in FMP free tier)
        t       = yf.Ticker(ticker)
        actions = t.actions.tail(10).to_dict() if not t.actions.empty else {}
        news    = t.news[:10] if t.news else []

        # If FMP profile returned nothing (unknown ticker / no key), fall back to yfinance
        if not profile:
            info = t.info or {}
            profile = {
                'sector':             info.get('sector'),
                'industry':           info.get('industry'),
                'market_cap':         info.get('marketCap'),
                'float_shares':       info.get('floatShares'),
                'shares_outstanding': info.get('sharesOutstanding'),
                'beta':               info.get('beta'),
                'current_price':      info.get('currentPrice') or info.get('regularMarketPrice'),
                '_source':            'yfinance_fallback',
            }

        # ── 2. Intraday chart (Polygon → yfinance) ───────────────────────────
        import os
        from config import Config
        from services.chart_service_research import build_session_chart

        storage_dir = os.path.join(Config.STORAGE_PATH, 'research')
        os.makedirs(storage_dir, exist_ok=True)

        image_paths = []
        chart_urls  = []

        if not date:
            date = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')

        bars_df = _fetch_intraday_polygon(ticker, date)

        if bars_df.empty:
            print(f"Polygon failed or empty for {date}. Falling back to yfinance.")
            from datetime import timedelta
            start_dt = datetime.strptime(date, '%Y-%m-%d')
            end_dt   = start_dt + timedelta(days=1)
            try:
                yf_df = yf.download(ticker,
                                    start=start_dt.strftime('%Y-%m-%d'),
                                    end=end_dt.strftime('%Y-%m-%d'),
                                    interval='5m', prepost=True, progress=False)
                if not yf_df.empty:
                    if hasattr(yf_df.columns, 'levels'):
                        yf_df.columns = yf_df.columns.get_level_values(0)
                    yf_df = yf_df.rename(columns={
                        'Open': 'open', 'High': 'high', 'Low': 'low',
                        'Close': 'close', 'Volume': 'volume',
                    })
                    bars_df = yf_df
                    print(f"yfinance fallback got {len(bars_df)} rows for {date}")
            except Exception as e:
                import traceback
                print(f"yfinance fallback failed: {e}")
                traceback.print_exc()

        if not bars_df.empty:
            try:
                filepath = build_session_chart(ticker, date, bars_df, job_id, storage_dir)
                filename = os.path.basename(filepath)
                image_paths.append(filepath)
                chart_urls.append(f"{base_url}/storage/charts/research/{filename}")
                print(f"Chart generated: {filepath}")
            except Exception as e:
                import traceback
                print(f"Failed to generate session chart: {e}")
                traceback.print_exc()
        else:
            print(f"No intraday data for {ticker} on {date}. Chart skipped.")

        # ── 3. Vision analysis ────────────────────────────────────────────────
        vision_analysis = None
        if image_paths:
            from llm.vision_client import analyze_charts_multi_tf
            vision_analysis = analyze_charts_multi_tf(ticker, image_paths)

        # ── 4. Build structured payload ───────────────────────────────────────
        payload = {
            'fundamentals': {
                'profile':           profile,
                'key_metrics_ttm':   key_m,
                'income_statement':  income,   # last 4 quarters
                'analyst_estimates': estimates,
            },
            'events': {
                'earnings_calendar': earnings,  # FMP: confirmed date + EPS estimate
                'recent_actions':    actions,
            },
            'news_headlines': [n.get('title') for n in news if n.get('title')],
            'technical_vision_analysis': vision_analysis or 'No technical vision analysis available.',
        }

        from llm.llm_client import get_ticker_deep_research

        def sanitize(obj):
            if isinstance(obj, dict):
                return {str(k): sanitize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize(i) for i in obj]
            elif hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return obj

        output, model = get_ticker_deep_research(ticker, sanitize(payload))

        if chart_urls:
            images_md = "\n".join([f"![{ticker} Chart]({url})" for url in chart_urls])
            output = f"### Technical Charts\n{images_md}\n\n---\n\n" + output

        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        import traceback
        traceback.print_exc()
        _set_status(job_id, 'error', output=str(e))


def _run_risk_detection(job_id: str, ticker: str):
    """Background worker: gather risk signals and generate Risk Detection report."""
    _set_status(job_id, 'running')
    try:
        from services.risk_service import build_risk_payload
        from llm.llm_client import get_risk_analysis

        payload = build_risk_payload(ticker)
        output, model = get_risk_analysis(ticker, payload)
        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        import traceback
        traceback.print_exc()
        _set_status(job_id, 'error', output=str(e))


def _run_catalyst_analysis(job_id: str, ticker: str, date: str):
    """Background worker: gather catalyst signals and generate Catalyst Analysis report."""
    _set_status(job_id, 'running')
    try:
        from services.catalyst_service import build_catalyst_payload
        from llm.llm_client import get_catalyst_analysis

        payload = build_catalyst_payload(ticker, date or None)
        output, model = get_catalyst_analysis(ticker, payload)
        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        import traceback
        traceback.print_exc()
        _set_status(job_id, 'error', output=str(e))


def _run_deep_context(job_id: str, ticker: str):
    """Background worker: gather technical/structural context and generate Deep Context report."""
    _set_status(job_id, 'running')
    try:
        from services.context_service import build_context_payload
        from llm.llm_client import get_deep_context

        payload = build_context_payload(ticker)
        output, model = get_deep_context(ticker, payload)
        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        import traceback
        traceback.print_exc()
        _set_status(job_id, 'error', output=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_job(job_id: str, jtype: str, input_ref: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO llm_jobs (id, type, status, input_ref) VALUES (%s, %s, 'pending', %s)",
            (job_id, jtype, input_ref),
        )


def _set_status(job_id: str, status: str, output: str = None, model_used: str = None):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE llm_jobs SET status=%s, output=%s, model_used=%s, updated_at=%s WHERE id=%s",
            (status, output, model_used, now, job_id),
        )
