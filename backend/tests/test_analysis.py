import pytest
import uuid
import datetime
from httpx import AsyncClient

# Force Celery to execute tasks eagerly (synchronously) during testing
from fastapi_app.celery_app import celery_app
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

from fastapi_app.db import get_pool

@pytest.mark.asyncio(loop_scope="session")
async def test_create_continuation_job(client: AsyncClient):
    # Ensure there's a date we can use
    payload = {"date": "2023-01-01"}
    response = await client.post("/api/continuation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["pending", "running", "done", "error"] # Eager execution changes status instantly

@pytest.mark.asyncio(loop_scope="session")
async def test_create_sentiment_job(client: AsyncClient):
    payload = {"query": "Is the market bullish?"}
    response = await client.post("/api/sentiment", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data

@pytest.mark.asyncio(loop_scope="session")
async def test_create_research_job(client: AsyncClient):
    payload = {"ticker": "AAPL", "date": "2023-01-01", "force": True}
    # Mocking actual deep research is hard because of external APIs.
    # The eager task will fail or succeed, but the API should return 200 immediately (or after eager exec).
    response = await client.post("/api/research", json=payload)
    assert response.status_code == 200
    assert "job_id" in response.json()

@pytest.mark.asyncio(loop_scope="session")
async def test_create_risk_detection(client: AsyncClient):
    payload = {"ticker": "TSLA", "force": True}
    response = await client.post("/api/research/risk", json=payload)
    assert response.status_code == 200
    assert "job_id" in response.json()

@pytest.mark.asyncio(loop_scope="session")
async def test_create_catalyst_analysis(client: AsyncClient):
    payload = {"ticker": "NVDA", "date": "2023-01-01", "force": True}
    response = await client.post("/api/research/catalyst", json=payload)
    assert response.status_code == 200
    assert "job_id" in response.json()

@pytest.mark.asyncio(loop_scope="session")
async def test_create_deep_context(client: AsyncClient):
    payload = {"ticker": "MSFT", "force": True}
    response = await client.post("/api/research/context", json=payload)
    assert response.status_code == 200
    assert "job_id" in response.json()

@pytest.mark.asyncio(loop_scope="session")
async def test_create_pipe_analysis(client: AsyncClient):
    payload = {"ticker": "GME", "date": "2023-01-01"}
    response = await client.post("/api/research/pipe", json=payload)
    assert response.status_code == 200
    assert "job_id" in response.json()

@pytest.mark.asyncio(loop_scope="session")
async def test_list_and_get_job(client: AsyncClient):
    # Create a job manually in DB first
    job_id = str(uuid.uuid4())
    async with get_pool().acquire() as conn:
        await conn.execute("INSERT INTO llm_jobs (id, type, status, input_ref) VALUES ($1, $2, $3, $4)",
                           job_id, 'test_type', 'pending', 'test_ref')
                           
    response = await client.get("/api/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert isinstance(jobs, list)
    assert any(j["id"] == job_id for j in jobs)

    response = await client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    job = response.json()
    assert job["id"] == job_id
    assert job["type"] == "test_type"

@pytest.mark.asyncio(loop_scope="session")
async def test_retry_job(client: AsyncClient):
    job_id = str(uuid.uuid4())
    async with get_pool().acquire() as conn:
        await conn.execute("INSERT INTO llm_jobs (id, type, status, input_ref) VALUES ($1, $2, $3, $4)",
                           job_id, 'sentiment', 'error', 'test_ref')
                           
    response = await client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] in ["pending", "running", "done", "error"]

@pytest.mark.asyncio(loop_scope="session")
async def test_archetypes(client: AsyncClient):
    response = await client.get("/api/archetypes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio(loop_scope="session")
async def test_research_history(client: AsyncClient):
    response = await client.get("/api/research/history?ticker=AAPL")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
@pytest.mark.asyncio(loop_scope="session")
async def test_get_and_export_cached_report(client: AsyncClient):
    # Insert a dummy report
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO research_cache (ticker, report_type, output, version) VALUES ($1, $2, $3, 1) RETURNING id",
            "DUMMY", "test_report", "test content"
        )
    cache_id = row['id']
    
    response = await client.get(f"/api/research/history/{cache_id}")
    assert response.status_code == 200
    assert response.json()["ticker"] == "DUMMY"
    
    response = await client.get(f"/api/research/export/{cache_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert "test content" in response.text
