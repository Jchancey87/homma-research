"""
tests/test_gainers.py
Phase 2 — async gainers router tests.
"""
import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_returns_200(client):
    resp = await client.get("/api/gainers")
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_returns_list(client):
    resp = await client.get("/api/gainers")
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_filter_min_gap(client):
    resp = await client.get("/api/gainers", params={"min_gap": 10})
    assert resp.status_code == 200
    data = resp.json()
    for row in data:
        assert row.get("gap_pct") is None or row["gap_pct"] >= 10


@pytest.mark.asyncio(loop_scope="session")
async def test_gainers_summary_shape(client):
    resp = await client.get("/api/gainers/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert "total" in body
    assert "gainers" in body
    assert isinstance(body["gainers"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_sectors_returns_list(client):
    resp = await client.get("/api/gainers/sectors")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_ticker_history_returns_200(client):
    resp = await client.get("/api/gainers/ticker-history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_ticker_history_sort_param(client):
    resp = await client.get("/api/gainers/ticker-history", params={"sort": "appearances", "limit": 5})
    assert resp.status_code == 200


@pytest.mark.asyncio(loop_scope="session")
async def test_float_buckets_shape(client):
    resp = await client.get("/api/gainers/float-buckets")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert "buckets" in body
    assert isinstance(body["buckets"], list)


@pytest.mark.asyncio(loop_scope="session")
async def test_sector_rotation_returns_list(client):
    resp = await client.get("/api/gainers/sector-rotation")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio(loop_scope="session")
async def test_export_returns_csv_content_type(client):
    resp = await client.get("/api/gainers/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


# ── /api/chart/live-price ──────────────────────────────────────────────────
# Backed by the live screener's in-memory cache.  Mock get_live_gainers so
# the tests are deterministic and don't depend on the background refresh loop.

MOCK_SNAPSHOT = {
    "session": "open",
    "session_label": "Open",
    "fetched_at": "2026-06-18T13:30:00Z",
    "gainers": [
        {"ticker": "AAPL",  "last_price": 178.45, "gap_pct": 1.2},
        {"ticker": "TSLA",  "last_price": 245.12, "gap_pct": 3.4},
        {"ticker": "NVDA",  "last_price": None,   "gap_pct": 0.0},
    ],
    "top_n": 25,
    "cache_ttl_s": 60,
}


def _install_mock_screener(monkeypatch):
    """Patch the live screener so the route's local import resolves to a stub."""
    from services import live_screener

    calls = {"n": 0}

    def _fake_get_live_gainers(force: bool = False):
        calls["n"] += 1
        return MOCK_SNAPSHOT

    monkeypatch.setattr(live_screener, "get_live_gainers", _fake_get_live_gainers)
    return calls


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_empty_param(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    resp = await client.get("/api/chart/live-price")
    assert resp.status_code == 200
    assert resp.json() == {"prices": {}}


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_empty_string(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    resp = await client.get("/api/chart/live-price", params={"tickers": ""})
    assert resp.status_code == 200
    assert resp.json() == {"prices": {}}


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_single_match(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    resp = await client.get("/api/chart/live-price", params={"tickers": "AAPL"})
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"prices": {"AAPL": 178.45}}


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_ticker_not_in_snapshot(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    resp = await client.get("/api/chart/live-price", params={"tickers": "ZZZZ"})
    assert resp.status_code == 200
    assert resp.json() == {"prices": {"ZZZZ": None}}


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_mixed(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    resp = await client.get(
        "/api/chart/live-price", params={"tickers": "AAPL,ZZZZ,TSLA,nvda"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "prices": {
            "AAPL": 178.45,
            "ZZZZ": None,
            "TSLA": 245.12,
            "NVDA": None,
        }
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_dedupes_and_normalizes(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    resp = await client.get(
        "/api/chart/live-price", params={"tickers": "aapl, AAPL, tsla"}
    )
    assert resp.status_code == 200
    body = resp.json()
    # Whitespace stripped, uppercased, deduped.
    assert body == {"prices": {"AAPL": 178.45, "TSLA": 245.12}}


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_cap_returns_400(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    big = ",".join(f"T{i:02d}" for i in range(51))
    resp = await client.get("/api/chart/live-price", params={"tickers": big})
    assert resp.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_chart_live_price_at_cap_is_allowed(client, monkeypatch):
    _install_mock_screener(monkeypatch)
    exactly_50 = ",".join(f"T{i:02d}" for i in range(50))
    resp = await client.get("/api/chart/live-price", params={"tickers": exactly_50})
    assert resp.status_code == 200
    body = resp.json()
    # None of these mock tickers are in the snapshot → all null.
    assert len(body["prices"]) == 50
    assert all(v is None for v in body["prices"].values())
