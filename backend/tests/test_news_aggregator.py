from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import pytest
from services.news_aggregator import FMPNewsSource, get_default_aggregator

def test_fmp_news_source_success():
    mock_articles = [
        {
            "symbol": "AAPL",
            "date": "2026-07-17 23:00:00",
            "title": "FMP News Article 1",
            "image": "https://example.com/image.png",
            "site": "GlobeNewswire",
            "text": "Some text about Apple winning a major contract.",
            "url": "https://example.com/article1"
        },
        {
            "symbol": "AAPL",
            "date": "2026-07-17 10:00:00",
            "title": "FMP News Article 2",
            "image": "https://example.com/image2.png",
            "site": "PR Newswire",
            "text": "Old news.",
            "url": "https://example.com/article2"
        }
    ]
    
    with patch("services.fmp_service.get_stock_news", return_value=mock_articles) as mock_get_stock_news:
        source = FMPNewsSource()
        fixed_now = datetime(2026, 7, 17, 23, 30, 0, tzinfo=timezone.utc)
        with patch("services.news_aggregator.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.strptime = datetime.strptime
            mock_dt.fromisoformat = datetime.fromisoformat
            
            res = source.get_news("AAPL", hours_back=4)
            
            assert len(res) == 1
            assert res[0]["title"] == "FMP News Article 1"
            assert res[0]["source"] == "fmp/GlobeNewswire"
            assert res[0]["description"] == "Some text about Apple winning a major contract."
            mock_get_stock_news.assert_called_once_with("AAPL", limit=20)

def test_fmp_news_source_exception():
    with patch("services.fmp_service.get_stock_news", side_effect=Exception("FMP Error")):
        source = FMPNewsSource()
        res = source.get_news("AAPL", hours_back=4)
        assert res == []

def test_get_default_aggregator_contains_fmp():
    agg = get_default_aggregator()
    source_names = [s.__class__.__name__ for s in agg.sources]
    assert "FMPNewsSource" in source_names
    assert source_names.index("FMPNewsSource") == 0
