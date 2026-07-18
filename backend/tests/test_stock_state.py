import pytest
from unittest.mock import patch
from datetime import date
from services.stock_state import StockState
from services.watchlist_service import enrich_watchlist_fundamentals
from fastapi_app.db import get_pool


def test_stock_state_gating_rules():
    """
    Test individual gating rules of StockState dataclass.
    """
    # 1. Active & Active status -> True
    s = StockState(ticker="XYZ", status="active", is_active=True)
    assert s.should_enrich(is_watchlist_member=True) is True
    assert s.should_enrich(is_watchlist_member=False) is True

    # 2. Inactive -> False
    s = StockState(ticker="XYZ", status="active", is_active=False)
    assert s.should_enrich(is_watchlist_member=True) is False
    assert s.should_enrich(is_watchlist_member=False) is False

    # 3. Suspended -> False
    s = StockState(ticker="XYZ", status="suspended", is_active=True)
    assert s.should_enrich(is_watchlist_member=True) is False
    assert s.should_enrich(is_watchlist_member=False) is False

    # 4. Restricted -> False
    s = StockState(ticker="XYZ", status="restricted", is_active=True)
    assert s.should_enrich(is_watchlist_member=True) is False
    assert s.should_enrich(is_watchlist_member=False) is False

    # 5. Watchlist-only -> depends on is_watchlist_member
    s = StockState(ticker="XYZ", status="watchlist_only", is_active=True)
    assert s.should_enrich(is_watchlist_member=True) is True
    assert s.should_enrich(is_watchlist_member=False) is False

    # 6. Unknown status -> False
    s = StockState(ticker="XYZ", status="unknown", is_active=True)
    assert s.should_enrich(is_watchlist_member=True) is False
    assert s.should_enrich(is_watchlist_member=False) is False


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_enrichment_state_gating(client):
    """
    Test integration of StockState gating rules with enrich_watchlist_fundamentals.
    """
    # Clean up first to avoid dirty state
    await client.delete("/api/watchlist/GATETEST")

    # Add GATETEST to the watchlist
    add_resp = await client.post(
        "/api/watchlist",
        json={"ticker": "GATETEST", "sector": "Biotech", "notes": "Init", "tags": ["test"]},
    )
    assert add_resp.status_code == 201

    pool = get_pool()
    async with pool.acquire() as conn:
        with patch("services.watchlist_service._fetch_single_ticker_metrics") as mock_fetch:
            mock_fetch.return_value = {
                "runway_months": 5.0,
                "dilution": "🔴 HIGH",
                "upcoming_catalyst": "Phase 3 test",
                "catalyst_date": date(2026, 12, 31),
            }

            # Case A: state is None (default behavior, should enrich)
            processed = await enrich_watchlist_fundamentals(conn, ticker="GATETEST", state=None)
            assert processed == 1
            assert mock_fetch.call_count == 1
            mock_fetch.reset_mock()

            # Case B: state is inactive (should skip enrichment)
            state_inactive = StockState(ticker="GATETEST", is_active=False)
            processed = await enrich_watchlist_fundamentals(conn, ticker="GATETEST", state=state_inactive)
            assert processed == 0
            assert mock_fetch.call_count == 0

            # Case C: state is restricted (should skip enrichment)
            state_restricted = StockState(ticker="GATETEST", status="restricted")
            processed = await enrich_watchlist_fundamentals(conn, ticker="GATETEST", state=state_restricted)
            assert processed == 0
            assert mock_fetch.call_count == 0

            # Case D: state is watchlist_only and ticker is a member (should enrich)
            state_wl_member = StockState(ticker="GATETEST", status="watchlist_only")
            processed = await enrich_watchlist_fundamentals(conn, ticker="GATETEST", state=state_wl_member)
            assert processed == 1
            assert mock_fetch.call_count == 1
            mock_fetch.reset_mock()

            # Case E: state is watchlist_only and ticker is NOT a member (should skip enrichment)
            state_wl_non_member = StockState(ticker="GATETEST_NON_MEMBER", status="watchlist_only")
            processed = await enrich_watchlist_fundamentals(
                conn, ticker="GATETEST_NON_MEMBER", state=state_wl_non_member
            )
            assert processed == 0
            assert mock_fetch.call_count == 0

    # Clean up
    await client.delete("/api/watchlist/GATETEST")
