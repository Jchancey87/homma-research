import os
import json
import time
from unittest.mock import patch, MagicMock
import pytest
from config import Config
from services.sec_service import get_cik_from_ticker, _cik_cache

@pytest.fixture(autouse=True)
def clear_cik_cache():
    _cik_cache.clear()
    yield
    _cik_cache.clear()

def test_get_cik_from_ticker_cache_hits(tmp_path):
    # Mock storage path to use tmp_path
    with patch.object(Config, "STORAGE_PATH", str(tmp_path)):
        # Create a pre-existing cache file
        cache_path = os.path.join(str(tmp_path), "sec_cik_map.json")
        mock_data = {"AAPL": "0000320193", "MSFT": "0000078901"}
        with open(cache_path, "w") as f:
            json.dump(mock_data, f)
            
        # Get CIK
        cik = get_cik_from_ticker("AAPL")
        assert cik == "0000320193"
        
        # Verify in-memory cache was updated
        assert _cik_cache["AAPL"] == "0000320193"
        assert _cik_cache["MSFT"] == "0000078901"

def test_get_cik_from_ticker_cache_miss_and_fetch(tmp_path):
    with patch.object(Config, "STORAGE_PATH", str(tmp_path)):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 78901, "ticker": "MSFT", "title": "Microsoft Corp."}
        }
        
        with patch("requests.get", return_value=mock_response) as mock_get:
            cik = get_cik_from_ticker("MSFT")
            assert cik == "0000078901"
            mock_get.assert_called_once()
            
            # Verify file was written to disk
            cache_path = os.path.join(str(tmp_path), "sec_cik_map.json")
            assert os.path.exists(cache_path)
            with open(cache_path, "r") as f:
                saved = json.load(f)
                assert saved["AAPL"] == "0000320193"
                assert saved["MSFT"] == "0000078901"
