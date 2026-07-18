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
