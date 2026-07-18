import pytest
from unittest.mock import patch, MagicMock
from datetime import date


@pytest.fixture(autouse=True)
def mock_enrichment_dependencies():
    with patch("services.watchlist_service._fetch_single_ticker_metrics") as mock_fetch:
        mock_fetch.return_value = {
            "runway_months": 5.0,
            "dilution": "🔴 HIGH",
            "upcoming_catalyst": "Phase 3 test",
            "catalyst_date": date(2026, 12, 31),
        }
        yield mock_fetch


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_enrichment_columns_db(client):
    # 1. Clean up first
    await client.delete("/api/watchlist/TESTENR")
    
    # 2. Add ticker to watchlist
    add_resp = await client.post(
        "/api/watchlist",
        json={"ticker": "TESTENR", "sector": "Biotech", "notes": "Init", "tags": ["test"]},
    )
    assert add_resp.status_code == 201

    # 3. Retrieve and verify default columns are present
    list_resp = await client.get("/api/watchlist")
    items = list_resp.json()
    item = next((i for i in items if i["ticker"] == "TESTENR"), None)
    assert item is not None
    assert "runway_months" in item
    assert "dilution_risk" in item
    assert "upcoming_catalyst" in item
    assert "catalyst_date" in item

    # 4. Clean up
    await client.delete("/api/watchlist/TESTENR")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_enrich_endpoint(client):
    # Add a temporary ticker
    await client.post(
        "/api/watchlist",
        json={"ticker": "TESTENR2", "sector": "Biotech", "notes": "Init", "tags": ["test"]},
    )
    
    resp = await client.post("/api/watchlist/enrich")
    assert resp.status_code == 202
    assert resp.json()["success"] is True

    # Clean up
    await client.delete("/api/watchlist/TESTENR2")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_export_import_new_fields(client):
    # Ensure no old items
    await client.delete("/api/watchlist/EXPENR")
    await client.delete("/api/watchlist/IMPENR")

    # Add item
    await client.post(
        "/api/watchlist",
        json={"ticker": "EXPENR", "sector": "Healthcare", "notes": "Notes", "tags": ["export"]},
    )
    
    resp = await client.get("/api/watchlist/export")
    assert resp.status_code == 200
    content = resp.text
    assert "runway_months" in content
    assert "dilution_risk" in content
    assert "upcoming_catalyst" in content
    assert "catalyst_date" in content
    
    # Test Import with new fields
    csv_content = (
        "ticker,sector,notes,tags,runway_months,dilution_risk,upcoming_catalyst,catalyst_date\n"
        "IMPENR,Biotech,imported enrichment,import,4.5,🔴 HIGH,PDUFA approval,2026-08-30\n"
    )
    
    import_resp = await client.post(
        "/api/watchlist/import",
        files={"file": ("test_import.csv", csv_content.encode("utf-8"), "text/csv")}
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["inserted"] == 1
    
    # Retrieve and verify import fields
    list_resp = await client.get("/api/watchlist")
    items = list_resp.json()
    imported_item = next((i for i in items if i["ticker"] == "IMPENR"), None)
    assert imported_item is not None
    assert imported_item["runway_months"] == 4.5
    assert imported_item["dilution_risk"] == "🔴 HIGH"
    assert imported_item["upcoming_catalyst"] == "PDUFA approval"
    assert imported_item["catalyst_date"] == "2026-08-30"
    
    # Clean up
    await client.delete("/api/watchlist/EXPENR")
    await client.delete("/api/watchlist/IMPENR")


@pytest.mark.asyncio(loop_scope="session")
async def test_watchlist_enrichment_caching_and_force(client):
    from fastapi_app.db import get_pool
    from services.watchlist_service import enrich_watchlist_fundamentals
    
    # 1. Clean up first
    await client.delete("/api/watchlist/CACHETEST")
    
    # 2. Add ticker to watchlist (explicitly with notes, sector, tags to avoid triggering auto-enrichment on insert)
    await client.post(
        "/api/watchlist",
        json={"ticker": "CACHETEST", "sector": "Biotech", "notes": "Init", "tags": ["test"]},
    )
    
    # Get database connection
    pool = get_pool()
    async with pool.acquire() as conn:
        # Clear out any previous metric updates
        await conn.execute("UPDATE watchlist SET last_enriched_at = NULL WHERE ticker = 'CACHETEST'")
        
        with patch("services.watchlist_service._fetch_single_ticker_metrics") as mock_fetch:
            mock_fetch.return_value = {
                "runway_months": 12.0,
                "dilution": "Low",
                "upcoming_catalyst": "Phase 2 readout",
                "catalyst_date": date(2026, 12, 31),
            }
            
            # First pass: not enriched yet (last_enriched_at is NULL). Should fetch.
            processed = await enrich_watchlist_fundamentals(conn, ticker="CACHETEST", force=False)
            assert processed == 1
            assert mock_fetch.call_count == 1
            
            # Second pass: last_enriched_at is now recent. Should be skipped when force=False.
            # Wait, when specific ticker is passed, enrich_watchlist_fundamentals defaults force to True!
            # So to test force=False gating, we must call it without a ticker parameter (bulk mode).
            mock_fetch.reset_mock()
            processed_bulk_cached = await enrich_watchlist_fundamentals(conn, force=False)
            # CACHETEST is in the watchlist and has a recent timestamp, so it must be skipped.
            # But other watchlist items might be stale, so let's verify CACHETEST specifically wasn't called.
            # We can check that the mock wasn't called with CACHETEST.
            for call in mock_fetch.call_args_list:
                assert call[0][0] != "CACHETEST"
                
            # Third pass: bulk enrichment with force=True should bypass the cache and fetch CACHETEST
            mock_fetch.reset_mock()
            await enrich_watchlist_fundamentals(conn, force=True)
            called_tickers = [call[0][0] for call in mock_fetch.call_args_list]
            assert "CACHETEST" in called_tickers
            
    # Clean up
    await client.delete("/api/watchlist/CACHETEST")

