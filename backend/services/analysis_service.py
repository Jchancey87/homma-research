"""
Analysis Service.

Business logic for LLM research job creation, report caching, and status tracking.
Follows RFC-001 thin router rules.
"""

from typing import Dict, List, Optional
import asyncpg


async def dispatch_research_job(
    db: asyncpg.Pool,
    ticker: str,
    date: Optional[str] = None,
    job_type: str = "continuation",
    force: bool = False
) -> dict:
    """Check cache or insert new pending LLM research job into jobs table."""
    if not force:
        cached_query = """
            SELECT report_text, version, created_at
            FROM llm_reports_cache
            WHERE ticker = $1 AND report_type = $2
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY created_at DESC LIMIT 1;
        """
        row = await db.fetchrow(cached_query, ticker, job_type)
        if row:
            return {
                "cached": True,
                "report": row["report_text"],
                "version": row["version"],
                "created_at": row["created_at"].isoformat(),
            }

    insert_query = """
        INSERT INTO jobs (type, status, input_ref)
        VALUES ($1, 'pending', $2)
        RETURNING id;
    """
    input_ref = f"{ticker}:{date}" if date else ticker
    job_id = await db.fetchval(insert_query, job_type, input_ref)
    return {"job_id": str(job_id), "status": "pending", "cached": False}
