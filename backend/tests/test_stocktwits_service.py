"""
test_stocktwits_service.py — Unit tests for StockTwits service.
"""
import pytest
from unittest.mock import patch, MagicMock
from services.stocktwits_service import get_stocktwits_sentiment, get_trending_symbols, _CACHE


def test_get_stocktwits_sentiment_success():
    _CACHE.clear()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "symbol": {
            "symbol": "UAMY",
            "title": "United States Antimony Corp.",
            "watchlist_count": 19879,
            "trending": True,
        },
        "messages": [
            {
                "id": 101,
                "body": "Great momentum on $UAMY!",
                "created_at": "2026-07-21T12:00:00Z",
                "user": {"username": "trader1", "followers": 150},
                "likes": {"total": 12},
                "entities": {"sentiment": {"basic": "Bullish"}},
            },
            {
                "id": 102,
                "body": "Taking profits here $UAMY",
                "created_at": "2026-07-21T12:01:00Z",
                "user": {"username": "trader2", "followers": 10},
                "likes": {"total": 2},
                "entities": {"sentiment": {"basic": "Bearish"}},
            },
            {
                "id": 103,
                "body": "Looking at charts",
                "created_at": "2026-07-21T12:02:00Z",
                "user": {"username": "trader3", "followers": 5},
                "likes": {"total": 0},
                "entities": {},
            },
        ],
    }

    with patch("requests.get", return_value=mock_response):
        data = get_stocktwits_sentiment("UAMY")

    assert data["ticker"] == "UAMY"
    assert data["title"] == "United States Antimony Corp."
    assert data["watchers_count"] == 19879
    assert data["is_trending"] is True
    assert data["message_count"] == 3
    assert data["bullish_count"] == 1
    assert data["bearish_count"] == 1
    assert data["bullish_ratio"] == 0.5
    assert len(data["top_messages"]) == 3
    assert data["top_messages"][0]["username"] == "trader1"


def test_get_stocktwits_sentiment_failure():
    _CACHE.clear()
    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("requests.get", return_value=mock_response):
        data = get_stocktwits_sentiment("INVALID")

    assert data["ticker"] == "INVALID"
    assert data["watchers_count"] == 0
    assert data["bullish_ratio"] is None


def test_get_trending_symbols():
    _CACHE.clear()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "symbols": [
            {"symbol": "NVDA", "title": "NVIDIA Corp", "watchlist_count": 600000, "trending_score": 99.5},
            {"symbol": "TSLA", "title": "Tesla Inc", "watchlist_count": 800000, "trending_score": 98.1},
        ]
    }

    with patch("requests.get", return_value=mock_response):
        trending = get_trending_symbols()

    assert len(trending) == 2
    assert trending[0]["symbol"] == "NVDA"
    assert trending[0]["watchlist_count"] == 600000
