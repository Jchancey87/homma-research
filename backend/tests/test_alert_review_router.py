"""
tests/test_alert_review_router.py
Integration tests for /alerts/review/* endpoints.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from fastapi_app.main import app
from fastapi_app.db import get_db

client = TestClient(app)

async def _mock_get_db():
    yield AsyncMock()

@pytest.fixture(autouse=True)
def override_db_dependency():
    app.dependency_overrides[get_db] = _mock_get_db
    yield
    app.dependency_overrides.clear()


@patch("services.alert_review_service.get_alert_review_summary", new_callable=AsyncMock)
def test_get_alert_review_summary_endpoint(mock_summary):
    mock_summary.return_value = {
        "date": "2026-06-01",
        "total_alerts": 5,
        "unique_symbols": 2,
        "tier_counts": {"Tier 1": 2, "Tier 2": 2, "Tier 3": 1},
        "alert_type_counts": {"NEAR_HOD_RADAR": 3, "BULL_FLAG": 2},
        "suppressed_count": 1,
        "mfe_15m_hit_rate": 66.7,
        "avg_mae_15m": -0.8,
    }

    res = client.get("/api/alerts/review/summary?date=2026-06-01")
    assert res.status_code == 200
    data = res.json()
    assert data["total_alerts"] == 5
    assert data["mfe_15m_hit_rate"] == 66.7


@patch("services.alert_review_service.get_alert_review_top10", new_callable=AsyncMock)
def test_get_alert_review_top10_endpoint(mock_top10):
    mock_top10.return_value = {
        "summary": {"date": "2026-06-01", "total_alerts": 1},
        "top10_gainers": [{"symbol": "NVDA", "best_15m_mfe": 4.5}],
    }

    res = client.get("/api/alerts/review/top10?date=2026-06-01")
    assert res.status_code == 200
    data = res.json()
    assert len(data["top10_gainers"]) == 1


@patch("services.alert_review_service.get_alert_review_detail", new_callable=AsyncMock)
def test_get_alert_review_detail_endpoint(mock_detail):
    mock_detail.return_value = {
        "symbol": "NVDA",
        "date": "2026-06-01",
        "chart": {"ohlcv": []},
        "alerts": [],
    }

    res = client.get("/api/alerts/review/detail?symbol=NVDA&date=2026-06-01")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "NVDA"
