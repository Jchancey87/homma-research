"""
fastapi_app/tasks/llm_tasks.py

Celery tasks for background LLM and data analysis jobs.
These tasks run in a synchronous environment (Celery worker process), so they
can safely use psycopg2 (database.get_connection) and synchronous API clients.
"""
import os
import traceback
import pytz
from datetime import datetime, timezone
import pandas as pd

from fastapi_app.celery_app import celery_app
from database import get_connection
from validation import EASTERN_TZ

# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_status(job_id: str, status: str, output: str = None, model_used: str = None):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "UPDATE llm_jobs SET status=%s, output=%s, model_used=%s, updated_at=%s WHERE id=%s",
            (status, output, model_used, now, job_id),
        )

def _cache_write(ticker: str, date: str | None, report_type: str, output: str, model_used: str, job_id: str):
    now = datetime.now(timezone.utc)
    
    # Let's redefine TTL locally to avoid circular import issues if routes/analysis is removed
    _CACHE_TTL = {
        'deep_research': 24,
        'risk':          72,
        'catalyst':       6,
        'context':       48,
        'pipe':          None,
    }
    
    ttl_hours = _CACHE_TTL.get(report_type)
    from datetime import timedelta
    expires_at = (now + timedelta(hours=ttl_hours)).isoformat() if ttl_hours else None

    # Get current version
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) as max_v FROM research_cache WHERE ticker=%s AND report_type=%s",
            (ticker, report_type)
        ).fetchone()
        version = (row['max_v'] if row else 0) + 1

        conn.execute(
            """INSERT INTO research_cache 
               (ticker, date, report_type, version, output, model_used, job_id, created_at, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (ticker, date, report_type, version, output, model_used, job_id, now.isoformat(), expires_at)
        )

from services.chart_data_service import _fetch_intraday_polygon  # noqa: E402,F401

# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.run_continuation")
def run_continuation(job_id: str, date: str):
    _set_status(job_id, 'running')
    try:
        with get_connection() as conn:
            gainer_rows = conn.execute(
                """SELECT ticker, gap_pct, float_shares, rvol_15m, sector,
                          news_headline, news_fresh, close_price, open_price
                   FROM daily_gainers WHERE date = %s
                   ORDER BY gap_pct DESC LIMIT 10""",
                (date,),
            ).fetchall()

            archetype_rows = conn.execute(
                """SELECT c.tags as tag,
                          COUNT(*) as count,
                          ROUND(AVG(d.gap_pct)::numeric, 1) as avg_gap_pct,
                          ROUND(AVG(d.rvol_15m)::numeric, 1) as avg_rvol,
                          ROUND(AVG(c.cleanliness_score)::numeric, 1) as avg_cleanliness
                   FROM chart_captures c
                   LEFT JOIN daily_gainers d ON c.ticker = d.ticker AND c.capture_date = d.date
                   WHERE c.tags IS NOT NULL AND c.tags != '[]'
                   GROUP BY c.tags
                   ORDER BY count DESC"""
            ).fetchall()

        if not gainer_rows:
            _set_status(job_id, 'error', output=f'No gainers found in the database for {date}. '
                        'Run the ingestion job or try a different date.')
            return

        from llm.llm_client import get_continuation_analysis
        from services.archetype_service import get_archetype_stats

        gainers        = [dict(r) for r in gainer_rows]
        archetype_stats = get_archetype_stats()

        output, model = get_continuation_analysis(date, gainers, archetype_stats)
        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        _set_status(job_id, 'error', output=str(e))


@celery_app.task(name="tasks.run_sentiment")
def run_sentiment(job_id: str, query: str):
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


@celery_app.task(name="tasks.run_deep_research")
def run_deep_research(job_id: str, ticker: str, date: str, base_url: str):
    import yfinance as yf
    _set_status(job_id, 'running')
    try:
        import sys
        import logging
        logging.getLogger(__name__).info(f"CELERY WORKER sys.path: {sys.path}")
        from services.fmp_service import (
            get_company_profile, get_analyst_estimates, get_income_statement,
            get_key_metrics, get_earnings_calendar as fmp_earnings,
            get_cash_position, get_insider_transactions, get_institutional_holders,
            get_stock_news as fmp_news,
        )

        profile    = get_company_profile(ticker)
        estimates  = get_analyst_estimates(ticker)
        income     = get_income_statement(ticker)
        key_m      = get_key_metrics(ticker)
        earnings   = fmp_earnings(ticker)
        cash       = get_cash_position(ticker)
        insider    = get_insider_transactions(ticker)
        holders    = get_institutional_holders(ticker)
        news_fmp   = fmp_news(ticker)

        t       = yf.Ticker(ticker)
        actions = t.actions.tail(10).to_dict() if not t.actions.empty else {}
        news    = t.news[:10] if t.news else []

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

        import os
        from config import Config
        from services.chart_service_research import build_session_chart

        storage_dir = os.path.join(Config.STORAGE_PATH, 'research')
        os.makedirs(storage_dir, exist_ok=True)

        image_paths = []
        chart_urls  = []

        if not date:
            date = datetime.now(EASTERN_TZ).strftime('%Y-%m-%d')

        bars_df = _fetch_intraday_polygon(ticker, date)

        if bars_df.empty:
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
            except Exception as e:
                print(f"yfinance fallback failed: {e}")

        if not bars_df.empty:
            try:
                filepath = build_session_chart(ticker, date, bars_df, job_id, storage_dir)
                filename = os.path.basename(filepath)
                image_paths.append(filepath)
                chart_urls.append(f"{base_url}/storage/charts/research/{filename}")
            except Exception as e:
                print(f"Failed to generate session chart: {e}")

        vision_analysis = None
        if image_paths:
            from llm.vision_client import analyze_charts_multi_tf
            vision_analysis = analyze_charts_multi_tf(ticker, image_paths)

        payload = {
            'fundamentals': {
                'profile':           profile,
                'key_metrics_ttm':   key_m,
                'income_statement':  income,
                'analyst_estimates': estimates,
                'cash_position':     cash,
                'insider_activity':  insider,
                'institutional':     holders,
            },
            'events': {
                'earnings_calendar': earnings,
                'recent_actions':    actions,
            },
            'news_headlines': {
                'yfinance': [n.get('title') for n in news if n.get('title')],
                'fmp':      [n.get('title') for n in news_fmp if n.get('title')],
            },
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
        _cache_write(ticker, date or None, 'deep_research', output, model, job_id)
    except Exception as e:
        tb = traceback.format_exc()
        _set_status(job_id, 'error', output=f"{str(e)}\n\n{tb}")


@celery_app.task(name="tasks.run_risk_detection")
def run_risk_detection(job_id: str, ticker: str):
    _set_status(job_id, 'running')
    try:
        from services.risk_service import build_risk_payload
        from llm.llm_client import get_risk_analysis

        payload = build_risk_payload(ticker)
        output, model = get_risk_analysis(ticker, payload)
        _set_status(job_id, 'done', output=output, model_used=model)
        _cache_write(ticker, None, 'risk', output, model, job_id)
    except Exception as e:
        _set_status(job_id, 'error', output=str(e))


@celery_app.task(name="tasks.run_catalyst_analysis")
def run_catalyst_analysis(job_id: str, ticker: str, date: str):
    _set_status(job_id, 'running')
    try:
        from services.catalyst_service import build_catalyst_payload
        from llm.llm_client import get_catalyst_analysis

        payload = build_catalyst_payload(ticker, date or None)
        output, model = get_catalyst_analysis(ticker, payload)
        _set_status(job_id, 'done', output=output, model_used=model)
        _cache_write(ticker, date or None, 'catalyst', output, model, job_id)
    except Exception as e:
        _set_status(job_id, 'error', output=str(e))


@celery_app.task(name="tasks.run_deep_context")
def run_deep_context(job_id: str, ticker: str):
    _set_status(job_id, 'running')
    try:
        from services.context_service import build_context_payload
        from llm.llm_client import get_deep_context

        payload = build_context_payload(ticker)
        output, model = get_deep_context(ticker, payload)
        _set_status(job_id, 'done', output=output, model_used=model)
        _cache_write(ticker, None, 'context', output, model, job_id)
    except Exception as e:
        _set_status(job_id, 'error', output=str(e))


@celery_app.task(name="tasks.run_pipe_analysis")
def run_pipe_analysis(job_id: str, ticker: str, date: str):
    _set_status(job_id, 'running')
    try:
        from services.pipe_service import build_pipe_payload
        from llm.llm_client import get_pipe_analysis

        payload = build_pipe_payload(ticker, date or None)
        output, model = get_pipe_analysis(ticker, payload)
        _set_status(job_id, 'done', output=output, model_used=model)
    except Exception as e:
        _set_status(job_id, 'error', output=str(e))
