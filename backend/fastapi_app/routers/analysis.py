"""
fastapi_app/routers/analysis.py
FastAPI port of routes/analysis.py
"""
import uuid
import asyncio
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncpg

from fastapi_app.db import get_db, row_to_dict, rows_to_list
from fastapi_app.tasks import llm_tasks

router = APIRouter(prefix="/analysis", tags=["analysis"]) # Wait, in Flask it was registered as /api/analysis or was it registered directly? Let's check main.py later. The plan says prefix="/api", and router is included under prefix="/api". The routes in Flask were /continuation, /research, etc.
# Wait! In Flask, `analysis_bp` had no prefix, it was registered in app.py as app.register_blueprint(analysis_bp, url_prefix='/api'). 
# In FastAPI, we'll just not use a prefix here and let main.py handle it, OR we'll use prefix="" 

# Let's redefine router to match exact Flask paths which were e.g. /api/continuation.
router = APIRouter(tags=["analysis"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class ContinuationJobBody(BaseModel):
    date: str

class SentimentJobBody(BaseModel):
    query: str

class TickerDateBody(BaseModel):
    ticker: str
    date: Optional[str] = None
    force: bool = False

class TickerOnlyBody(BaseModel):
    ticker: str
    force: bool = False

# ── DB Helpers ────────────────────────────────────────────────────────────────

async def _create_job(conn: asyncpg.Connection, job_id: str, jtype: str, input_ref: str):
    await conn.execute(
        "INSERT INTO llm_jobs (id, type, status, input_ref) VALUES ($1, $2, 'pending', $3)",
        job_id, jtype, input_ref
    )

async def _cache_read(conn: asyncpg.Connection, ticker: str, d: Optional[str], report_type: str) -> Optional[dict]:
    now = datetime.utcnow()
    date_str = d if d else None
    if date_str:
        sql = """
            SELECT * FROM research_cache 
            WHERE ticker=$1 AND date=$2 AND report_type=$3 
            AND (expires_at IS NULL OR expires_at > $4) 
            ORDER BY created_at DESC LIMIT 1
        """
        row = await conn.fetchrow(sql, ticker, date_str, report_type, now)
    else:
        sql = """
            SELECT * FROM research_cache 
            WHERE ticker=$1 AND report_type=$2 
            AND (expires_at IS NULL OR expires_at > $3) 
            ORDER BY created_at DESC LIMIT 1
        """
        row = await conn.fetchrow(sql, ticker, report_type, now)
    return row_to_dict(row)

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/continuation")
async def start_continuation(data: ContinuationJobBody, conn: asyncpg.Connection = Depends(get_db)):
    date_str = data.date
    job_id = str(uuid.uuid4())
    await _create_job(conn, job_id, 'continuation', date_str)
    llm_tasks.run_continuation.delay(job_id, date_str)
    return {"job_id": job_id, "status": "pending"}

@router.post("/sentiment")
async def start_sentiment(data: SentimentJobBody, conn: asyncpg.Connection = Depends(get_db)):
    job_id = str(uuid.uuid4())
    await _create_job(conn, job_id, 'sentiment', data.query[:200])
    llm_tasks.run_sentiment.delay(job_id, data.query)
    return {"job_id": job_id, "status": "pending"}

@router.post("/research")
async def start_research(data: TickerDateBody, request: Request, conn: asyncpg.Connection = Depends(get_db)):
    if not data.force:
        cached = await _cache_read(conn, data.ticker, data.date, 'deep_research')
        if cached:
            return {
                "cached": True,
                "report": cached['output'],
                "version": cached['version'],
                "created_at": str(cached['created_at'])
            }

    job_id = str(uuid.uuid4())
    await _create_job(conn, job_id, 'research', data.ticker)
    
    # Base URL for images
    base_url = str(request.base_url).rstrip('/')
    date_str = data.date if data.date else ''
    llm_tasks.run_deep_research.delay(job_id, data.ticker, date_str, base_url)
    
    return {"job_id": job_id, "status": "pending"}

@router.post("/research/risk")
async def start_risk_detection(data: TickerOnlyBody, conn: asyncpg.Connection = Depends(get_db)):
    if not data.force:
        cached = await _cache_read(conn, data.ticker, None, 'risk')
        if cached:
            return {
                "cached": True,
                "report": cached['output'],
                "version": cached['version'],
                "created_at": str(cached['created_at'])
            }

    job_id = str(uuid.uuid4())
    await _create_job(conn, job_id, 'risk_detection', data.ticker)
    llm_tasks.run_risk_detection.delay(job_id, data.ticker)
    return {"job_id": job_id, "status": "pending"}

@router.post("/research/catalyst")
async def start_catalyst_analysis(data: TickerDateBody, conn: asyncpg.Connection = Depends(get_db)):
    if not data.force:
        cached = await _cache_read(conn, data.ticker, data.date, 'catalyst')
        if cached:
            return {
                "cached": True,
                "report": cached['output'],
                "version": cached['version'],
                "created_at": str(cached['created_at'])
            }

    job_id = str(uuid.uuid4())
    await _create_job(conn, job_id, 'catalyst_analysis', data.ticker)
    date_str = data.date if data.date else ''
    llm_tasks.run_catalyst_analysis.delay(job_id, data.ticker, date_str)
    return {"job_id": job_id, "status": "pending"}

@router.post("/research/context")
async def start_deep_context(data: TickerOnlyBody, conn: asyncpg.Connection = Depends(get_db)):
    if not data.force:
        cached = await _cache_read(conn, data.ticker, None, 'context')
        if cached:
            return {
                "cached": True,
                "report": cached['output'],
                "version": cached['version'],
                "created_at": str(cached['created_at'])
            }

    job_id = str(uuid.uuid4())
    await _create_job(conn, job_id, 'deep_context', data.ticker)
    llm_tasks.run_deep_context.delay(job_id, data.ticker)
    return {"job_id": job_id, "status": "pending"}

@router.post("/research/pipe")
async def start_pipe_analysis(data: TickerDateBody, conn: asyncpg.Connection = Depends(get_db)):
    job_id = str(uuid.uuid4())
    await _create_job(conn, job_id, 'pipe_analysis', data.ticker)
    date_str = data.date if data.date else ''
    llm_tasks.run_pipe_analysis.delay(job_id, data.ticker, date_str)
    return {"job_id": job_id, "status": "pending"}

@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, request: Request, conn: asyncpg.Connection = Depends(get_db)):
    row = await conn.fetchrow("SELECT * FROM llm_jobs WHERE id = $1", job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    job = row_to_dict(row)
    if job['status'] not in ('error', 'running'):
        raise HTTPException(status_code=400, detail=f"Cannot retry a job with status '{job['status']}'")

    jtype = job['type']
    input_ref = job.get('input_ref', '')

    await conn.execute(
        "UPDATE llm_jobs SET status='pending', output=NULL, updated_at=$1 WHERE id=$2",
        datetime.utcnow(), job_id
    )

    base_url = str(request.base_url).rstrip('/')

    if jtype == 'continuation':
        llm_tasks.run_continuation.delay(job_id, input_ref)
    elif jtype == 'sentiment':
        llm_tasks.run_sentiment.delay(job_id, input_ref)
    elif jtype == 'research':
        llm_tasks.run_deep_research.delay(job_id, input_ref, '', base_url)
    elif jtype == 'risk_detection':
        llm_tasks.run_risk_detection.delay(job_id, input_ref)
    elif jtype == 'catalyst_analysis':
        llm_tasks.run_catalyst_analysis.delay(job_id, input_ref, '')
    elif jtype == 'deep_context':
        llm_tasks.run_deep_context.delay(job_id, input_ref)
    elif jtype == 'pipe_analysis':
        llm_tasks.run_pipe_analysis.delay(job_id, input_ref, '')
    else:
        raise HTTPException(status_code=400, detail=f"Unknown job type '{jtype}' — cannot retry")

    return {"job_id": job_id, "status": "pending"}

@router.get("/jobs")
async def list_jobs(
    type: Optional[str] = None, 
    limit: int = 50, 
    conn: asyncpg.Connection = Depends(get_db)
):
    if type:
        rows = await conn.fetch("SELECT * FROM llm_jobs WHERE type = $1 ORDER BY created_at DESC LIMIT $2", type, limit)
    else:
        rows = await conn.fetch("SELECT * FROM llm_jobs ORDER BY created_at DESC LIMIT $1", limit)
    return rows_to_list(rows)

@router.get("/jobs/{job_id}")
async def get_job(job_id: str, conn: asyncpg.Connection = Depends(get_db)):
    row = await conn.fetchrow("SELECT * FROM llm_jobs WHERE id = $1", job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row_to_dict(row)

@router.get("/research/history")
async def research_history(
    ticker: str,
    type: Optional[str] = None,
    limit: int = 50,
    conn: asyncpg.Connection = Depends(get_db)
):
    if type:
        rows = await conn.fetch(
            "SELECT id, ticker, date, report_type, version, model_used, created_at, expires_at FROM research_cache WHERE ticker = $1 AND report_type = $2 ORDER BY created_at DESC LIMIT $3",
            ticker, type, limit
        )
    else:
        rows = await conn.fetch(
            "SELECT id, ticker, date, report_type, version, model_used, created_at, expires_at FROM research_cache WHERE ticker = $1 ORDER BY created_at DESC LIMIT $2",
            ticker, limit
        )
    return rows_to_list(rows)

@router.get("/research/history/{cache_id}")
async def get_cached_report(cache_id: int, conn: asyncpg.Connection = Depends(get_db)):
    row = await conn.fetchrow("SELECT * FROM research_cache WHERE id = $1", cache_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cached report not found")
    return row_to_dict(row)

@router.get("/research/export/{cache_id}")
async def export_cached_report(cache_id: int, conn: asyncpg.Connection = Depends(get_db)):
    row = await conn.fetchrow(
        "SELECT ticker, date, report_type, version, output, created_at FROM research_cache WHERE id = $1",
        cache_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cached report not found")
    
    r = row_to_dict(row)
    filename = f"{r['ticker']}_{r['report_type']}_v{r['version']}_{(r['date'] or str(r['created_at'])[:10])}.md"
    header = f"# {r['ticker']} — {r['report_type'].replace('_', ' ').title()} (v{r['version']})\n"
    header += f"_Generated: {r['created_at']}_\n\n---\n\n"
    content = header + (r['output'] or '')

    # StreamingResponse is used in FastAPI to return files dynamically
    from io import BytesIO
    stream = BytesIO(content.encode('utf-8'))
    return StreamingResponse(
        stream,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/archetypes")
async def get_archetypes(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch(
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
    )
    return rows_to_list(rows)

@router.get("/research/chart-data")
async def get_chart_data(
    ticker: str,
    date: date,
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Return OHLCV + all indicator series as JSON for the interactive Lightweight Charts frontend.
    This queries TimescaleDB first, then falls back to live API fetching (Polygon/yfinance).
    """
    import pytz
    from datetime import datetime, time
    
    ticker_val = ticker.upper().strip()
    date_str = date.isoformat()
    
    # Try to fetch from internal TimescaleDB
    db_bars = None
    try:
        eastern = pytz.timezone('US/Eastern')
        start_dt = eastern.localize(datetime.combine(date, time.min))
        end_dt = eastern.localize(datetime.combine(date, time.max))
        
        rows = await db.fetch(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM price_history_1min
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp <= $3
            ORDER BY timestamp ASC
            """,
            ticker_val,
            start_dt,
            end_dt
        )
        if rows:
            db_bars = [
                {
                    "time": r["timestamp"],
                    "open": r["open"],
                    "high": r["high"],
                    "low": r["low"],
                    "close": r["close"],
                    "volume": r["volume"]
                }
                for r in rows
            ]
    except Exception as exc:
        log.error("Failed to query price_history_1min for chart-data: %s", exc)

    def _compute_chart_data(db_bars=None):
        import pandas as pd
        import numpy as np
        from fastapi_app.tasks.llm_tasks import _fetch_intraday_polygon

        if db_bars:
            bars_df = pd.DataFrame(db_bars)
            bars_df.set_index('time', inplace=True)
        else:
            bars_df = _fetch_intraday_polygon(ticker_val, date_str)

            if bars_df.empty:
                try:
                    import yfinance as yf
                    from datetime import timedelta, datetime as dt_class
                    start_dt = dt_class.strptime(date_str, '%Y-%m-%d')
                    end_dt   = start_dt + timedelta(days=1)
                    yf_df = yf.download(ticker_val,
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
                    pass

            if bars_df.empty:
                try:
                    from datetime import timedelta, datetime as dt_class
                    prev_date = (dt_class.strptime(date_str, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                    bars_df = _fetch_intraday_polygon(ticker_val, prev_date)
                    if bars_df.empty:
                        import yfinance as yf
                        start_dt = dt_class.strptime(prev_date, '%Y-%m-%d')
                        end_dt   = start_dt + timedelta(days=1)
                        bars_df = yf.download(ticker_val, start=start_dt.strftime('%Y-%m-%d'),
                                             end=end_dt.strftime('%Y-%m-%d'),
                                             interval='1m', prepost=True, progress=False)
                        if not bars_df.empty and hasattr(bars_df.columns, 'levels'):
                            bars_df.columns = bars_df.columns.get_level_values(0)
                            bars_df = bars_df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
                except: pass

        if bars_df.empty:
            return None

        df = bars_df[['open', 'high', 'low', 'close', 'volume']].copy()

        if hasattr(df.index, 'tz') and df.index.tz is not None:
            df.index = df.index.tz_convert('UTC')
        else:
            df.index = df.index.tz_localize('UTC', ambiguous='infer', nonexistent='shift_forward')
        epoch = pd.Timestamp('1970-01-01', tz='UTC')
        df['time'] = ((df.index - epoch).total_seconds()).astype(int)

        for span in [8, 13, 21, 34, 55]:
            df[f'ema_{span}'] = df['close'].ewm(span=span, adjust=False).mean()

        vol_avg = df['volume'].rolling(20).mean()
        df['rvol'] = (df['volume'] / vol_avg).fillna(1.0)

        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift(1)).abs()
        tr3 = (df['low']  - df['close'].shift(1)).abs()
        tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['atr'] = tr.ewm(alpha=1/14, adjust=False).mean()

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

        vol_colors = ['rgba(34,211,167,0.5)' if c >= o else 'rgba(240,77,90,0.5)'
                      for c, o in zip(df['close'], df['open'])]

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

        return {
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
        }
        
    result = await asyncio.to_thread(_compute_chart_data, db_bars)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No intraday data available for {ticker} on {date_str}")
    return result
