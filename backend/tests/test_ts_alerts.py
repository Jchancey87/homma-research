"""
Unit tests for backend/fastapi_app/routers/ts_alerts.py and ALERTS_DISABLED kill switch.
"""
from unittest.mock import patch, MagicMock
import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_app.routers.ts_alerts import router as ts_alerts_router, _parse_ts_time, TSAlertRecord
from fastapi_app.tasks.alerts import send_telegram_alert_task, send_telegram_message


app = FastAPI()
app.include_router(ts_alerts_router)
client = TestClient(app)


def test_alerts_disabled_kill_switch():
    """Verify that when ALERTS_DISABLED is True, telegram tasks skip execution."""
    with patch("fastapi_app.tasks.alerts.ALERTS_DISABLED", True):
        msg_res = send_telegram_message("Test message")
        assert msg_res is False

        alert_res = send_telegram_alert_task({"symbol": "AAPL", "alert_type": "VOLUME_SPIKE"})
        assert alert_res == {"status": "skipped", "reason": "alerts_disabled"}


def test_parse_ts_time():
    """Verify timestamp parsing formats for TradeStation logs."""
    dt1 = _parse_ts_time("2026-08-06 09:30:00")
    assert isinstance(dt1, datetime)
    assert dt1.year == 2026

    dt2 = _parse_ts_time("2026-08-06T14:45:10.123")
    assert isinstance(dt2, datetime)

    with pytest.raises(ValueError):
        _parse_ts_time("invalid-time-format")


def test_get_expected_fields():
    """Verify GET /ts-alerts/fields endpoint."""
    response = client.get("/ts-alerts/fields")
    assert response.status_code == 200
    data = response.json()
    assert "csv_fields" in data
    assert "symbol" in data["csv_fields"]
    assert "price" in data["csv_fields"]
