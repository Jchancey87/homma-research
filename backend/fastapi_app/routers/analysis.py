"""
fastapi_app/routers/analysis.py
FastAPI port of routes/analysis.py
"""
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
import asyncpg

log = logging.getLogger(__name__)

from fastapi_app.db import get_db, row_to_dict, rows_to_list
from fastapi_app.tasks import llm_tasks
from services.chart_data_service import get_chart_data as _get_chart_data, ChartDataNotFoundError

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
    mini: bool = Query(False, description="If True, return only ohlcv, volume, and ema_21"),
    db: asyncpg.Connection = Depends(get_db)
):
    """
    Return OHLCV + all indicator series as JSON for the interactive Lightweight Charts frontend.
    Delegates to services.chart_data_service.get_chart_data which owns the
    DB read, fallback chain, indicator math, and cache write.
    """
    try:
        return await _get_chart_data(db, ticker, date, mini)
    except ChartDataNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
