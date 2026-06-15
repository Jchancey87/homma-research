"""
tests/test_live_quotes_service.py
Unit tests for services/live_quotes_service.py.

The pure shape-unwrap helpers and Polygon adapter are tested in isolation
with mocked responses. The end-to-end happy path (router → service →
response shape) is covered by the existing tests/test_continuation.py,
test_watchlist.py, test_gainers.py, test_market.py — those exercise the
full HTTP surface and assert on the per-router field names.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
_REPO = _BACKEND.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.live_quotes_service import (  # noqa: E402
    NormalizedQuote,
    _polygon_fetch_one_sync,
    _quote_from_polygon,
    _quote_from_schwab,
    get_live_quotes,
)


# ── NormalizedQuote dataclass ─────────────────────────────────────────────────

def test_normalized_quote_defaults_are_none_and_none_source():
    nq = NormalizedQuote(ticker="AAPL")
    assert nq.ticker == "AAPL"
    assert nq.last_price is None
    assert nq.open_price is None
    assert nq.volume is None
    assert nq.change_pct is None
    assert nq.prev_close is None
    assert nq.source == "none"


def test_normalized_quote_as_dict_round_trip():
    nq = NormalizedQuote(ticker="AAPL", last_price=10.0, source="schwab")
    d = nq.as_dict()
    assert d == {
        "ticker": "AAPL",
        "last_price": 10.0,
        "open_price": None,
        "volume": None,
        "change_pct": None,
        "prev_close": None,
        "source": "schwab",
    }


# ── _quote_from_schwab ────────────────────────────────────────────────────────

def test_schwab_unwrap_happy_path():
    payload = {
        "quote": {
            "lastPrice": 12.34,
            "openPrice": 11.0,
            "totalVolume": 1_500_000,
            "netPercentChange": 8.5,
            "closePrice": 11.5,
        }
    }
    nq = _quote_from_schwab("AAPL", payload)
    assert nq is not None
    assert nq.ticker == "AAPL"
    assert nq.last_price == 12.34
    assert nq.open_price == 11.0
    assert nq.volume == 1_500_000
    assert nq.change_pct == 8.5
    assert nq.prev_close == 11.5
    assert nq.source == "schwab"


def test_schwab_unwrap_missing_quote_returns_none():
    assert _quote_from_schwab("X", {}) is None
    assert _quote_from_schwab("X", {"quote": {}}) is None


def test_schwab_unwrap_missing_last_price_returns_none():
    """Halted/OTC symbols come back with quote fields but no lastPrice."""
    assert _quote_from_schwab("X", {"quote": {"openPrice": 1.0}}) is None


def test_schwab_unwrap_handles_none_payload():
    assert _quote_from_schwab("X", None) is None


# ── _quote_from_polygon ───────────────────────────────────────────────────────

def test_polygon_unwrap_happy_path():
    snap = {
        "ticker": {
            "day": {"o": 11.0, "h": 12.5, "l": 10.5, "c": 12.34, "v": "1500000"},
            "prevDay": {"c": 11.5, "v": "1000000"},
            "last": {"p": 12.34},
        }
    }
    nq = _quote_from_polygon("AAPL", snap)
    assert nq is not None
    assert nq.last_price == 12.34
    assert nq.open_price == 11.0
    assert nq.volume == 1_500_000
    assert nq.change_pct == round((12.34 - 11.5) / 11.5 * 100, 2)
    assert nq.prev_close == 11.5
    assert nq.source == "polygon"


def test_polygon_unwrap_missing_close_returns_none():
    assert _quote_from_polygon("X", {"ticker": {"day": {"o": 11.0}}}) is None
    assert _quote_from_polygon("X", {"ticker": {}}) is None


def test_polygon_unwrap_no_change_pct_when_prev_missing():
    snap = {"ticker": {"day": {"c": 12.34, "v": 1000}, "prevDay": {}}}
    nq = _quote_from_polygon("X", snap)
    assert nq is not None
    assert nq.last_price == 12.34
    assert nq.change_pct is None
    assert nq.prev_close is None


def test_polygon_unwrap_handles_garbage_volume():
    snap = {"ticker": {"day": {"c": 1.0, "v": "not-a-number"}, "prevDay": {"c": 0.95}}}
    nq = _quote_from_polygon("X", snap)
    assert nq is not None
    assert nq.volume is None


def test_polygon_unwrap_handles_top_level_dict():
    """Some Polygon responses omit the 'ticker' wrapper for single-ticker lookups."""
    snap = {"day": {"c": 5.0, "v": 100}, "prevDay": {"c": 4.0}}
    nq = _quote_from_polygon("X", snap)
    assert nq is not None
    assert nq.last_price == 5.0
    assert nq.change_pct == 25.0


def test_polygon_unwrap_handles_non_dict():
    assert _quote_from_polygon("X", None) is None
    assert _quote_from_polygon("X", "not a dict") is None
    assert _quote_from_polygon("X", 42) is None


# ── _polygon_fetch_one_sync ──────────────────────────────────────────────────

def test_polygon_fetch_one_sync_happy_path():
    fake_resp = MagicMock()
    fake_resp.ok = True
    fake_resp.json.return_value = {"ticker": {"day": {"c": 1.0}}}
    with patch("requests.get", return_value=fake_resp) as mock_get:
        result = _polygon_fetch_one_sync("AAPL", "key123")
    assert result == {"ticker": {"day": {"c": 1.0}}}
    mock_get.assert_called_once()
    called_url = mock_get.call_args[0][0]
    assert "AAPL" in called_url
    assert "polygon.io" in called_url
    assert mock_get.call_args.kwargs.get("params", {}).get("apiKey") == "key123"


def test_polygon_fetch_one_sync_non_ok_returns_none():
    fake_resp = MagicMock()
    fake_resp.ok = False
    fake_resp.status_code = 429
    with patch("requests.get", return_value=fake_resp):
        assert _polygon_fetch_one_sync("AAPL", "key123") is None


def test_polygon_fetch_one_sync_request_exception_returns_none():
    import requests as _req
    with patch("requests.get", side_effect=_req.Timeout()):
        assert _polygon_fetch_one_sync("AAPL", "key123") is None


# ── get_live_quotes (async, mocked) ──────────────────────────────────────────

async def test_get_live_quotes_schwab_full_coverage():
    """All tickers returned by Schwab → Polygon never called."""
    schwab_payload = {
        "AAPL": {"quote": {"lastPrice": 100.0, "openPrice": 99.0,
                           "totalVolume": 1000, "netPercentChange": 1.0}},
        "MSFT": {"quote": {"lastPrice": 200.0, "openPrice": 198.0,
                           "totalVolume": 2000, "netPercentChange": 2.0}},
    }
    with patch("services.schwab_client.get_quotes", return_value=schwab_payload) as mock_get, \
         patch("services.live_quotes_service._polygon_fetch_one_sync") as mock_poly:
        out = await get_live_quotes(["AAPL", "MSFT"], polygon_api_key="key123")
    assert set(out.keys()) == {"AAPL", "MSFT"}
    assert out["AAPL"].last_price == 100.0
    assert out["AAPL"].source == "schwab"
    assert out["MSFT"].last_price == 200.0
    assert out["MSFT"].source == "schwab"
    mock_get.assert_called_once_with(["AAPL", "MSFT"])
    mock_poly.assert_not_called()


async def test_get_live_quotes_schwab_partial_polygon_fills_gap():
    """Schwab returns AAPL but not MSFT → Polygon called only for MSFT."""
    schwab_payload = {
        "AAPL": {"quote": {"lastPrice": 100.0, "totalVolume": 1000}},
    }
    polygon_snap = {"ticker": {"day": {"c": 200.0, "v": 5000},
                                "prevDay": {"c": 198.0}}}
    with patch("services.schwab_client.get_quotes", return_value=schwab_payload), \
         patch("services.live_quotes_service._polygon_fetch_one_sync",
               return_value=polygon_snap) as mock_poly:
        out = await get_live_quotes(["AAPL", "MSFT"], polygon_api_key="key123")
    assert out["AAPL"].source == "schwab"
    assert out["MSFT"].source == "polygon"
    assert out["MSFT"].last_price == 200.0
    assert out["MSFT"].change_pct == round((200 - 198) / 198 * 100, 2)
    # Polygon called exactly once, only for MSFT
    assert mock_poly.call_count == 1
    assert mock_poly.call_args[0][0] == "MSFT"
    assert mock_poly.call_args[0][1] == "key123"


async def test_get_live_quotes_schwab_failure_falls_through_to_polygon():
    """Schwab raises → Polygon handles all tickers."""
    polygon_snap_aapl = {"ticker": {"day": {"c": 100.0, "v": 1000},
                                    "prevDay": {"c": 99.0}}}
    polygon_snap_msft = {"ticker": {"day": {"c": 200.0, "v": 2000},
                                    "prevDay": {"c": 199.0}}}

    def _fake_poly(ticker, key):
        return polygon_snap_aapl if ticker == "AAPL" else polygon_snap_msft

    with patch("services.schwab_client.get_quotes",
               side_effect=Exception("auth expired")), \
         patch("services.live_quotes_service._polygon_fetch_one_sync",
               side_effect=_fake_poly) as mock_poly:
        out = await get_live_quotes(["AAPL", "MSFT"], polygon_api_key="key123")
    assert out["AAPL"].source == "polygon"
    assert out["MSFT"].source == "polygon"
    assert out["AAPL"].last_price == 100.0
    assert out["MSFT"].last_price == 200.0
    assert {c.args[0] for c in mock_poly.call_args_list} == {"AAPL", "MSFT"}


async def test_get_live_quotes_no_polygon_key_yields_empty_for_missing():
    """Schwab misses MSFT and no Polygon key → MSFT fields all None."""
    schwab_payload = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    with patch("services.schwab_client.get_quotes", return_value=schwab_payload), \
         patch("services.live_quotes_service._polygon_fetch_one_sync") as mock_poly:
        out = await get_live_quotes(["AAPL", "MSFT"], polygon_api_key=None)
    assert out["AAPL"].last_price == 100.0
    assert out["MSFT"].last_price is None
    assert out["MSFT"].open_price is None
    assert out["MSFT"].change_pct is None
    assert out["MSFT"].source == "none"
    mock_poly.assert_not_called()


async def test_get_live_quotes_empty_polygon_key_treated_as_none():
    schwab_payload = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    with patch("services.schwab_client.get_quotes", return_value=schwab_payload), \
         patch("services.live_quotes_service._polygon_fetch_one_sync") as mock_poly:
        out = await get_live_quotes(["AAPL", "MSFT"], polygon_api_key="")
    assert out["MSFT"].source == "none"
    mock_poly.assert_not_called()


async def test_get_live_quotes_empty_input_returns_empty_dict():
    out = await get_live_quotes([], polygon_api_key="key")
    assert out == {}


async def test_get_live_quotes_none_input_returns_empty_dict():
    out = await get_live_quotes(None, polygon_api_key="key")
    assert out == {}


async def test_get_live_quotes_deduplicates_tickers():
    """Input has duplicates → one Schwab lookup, one result key per unique ticker (case-insensitive)."""
    schwab_payload = {"AAPL": {"quote": {"lastPrice": 100.0}}}
    with patch("services.schwab_client.get_quotes",
               return_value=schwab_payload) as mock_get:
        out = await get_live_quotes(["AAPL", "AAPL", "aapl"], polygon_api_key=None)
    assert set(out.keys()) == {"AAPL"}  # first-seen casing wins, "aapl" collapsed
    assert out["AAPL"].last_price == 100.0
    # Schwab called once with single-ticker de-duplicated list
    mock_get.assert_called_once_with(["AAPL"])


async def test_get_live_quotes_polygon_failure_yields_empty_quote():
    """Schwab misses + Polygon returns None → NormalizedQuote with all None."""
    schwab_payload: dict = {}
    with patch("services.schwab_client.get_quotes", return_value=schwab_payload), \
         patch("services.live_quotes_service._polygon_fetch_one_sync",
               return_value=None):
        out = await get_live_quotes(["AAPL"], polygon_api_key="key123")
    assert out["AAPL"].source == "none"
    assert out["AAPL"].last_price is None
