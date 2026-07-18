from unittest.mock import patch, MagicMock
import pytest
from fastapi_app.tasks.alerts import send_telegram_alert_task
from llm.llm_client import get_headline_sentiment


def test_get_headline_sentiment_success():
    with patch("llm.llm_client.Config") as mock_config:
        mock_config.LLM_API_KEY = "fake_key"
        with patch("llm.llm_client._chat", return_value="BULLISH") as mock_chat:
            res = get_headline_sentiment(["Good news headline"])
            assert res == "BULLISH"
            mock_chat.assert_called_once()


def test_get_headline_sentiment_empty():
    res = get_headline_sentiment([])
    assert res == "NEUTRAL"


def test_get_headline_sentiment_error():
    with patch("llm.llm_client.Config") as mock_config:
        mock_config.LLM_API_KEY = "fake_key"
        with patch("llm.llm_client._chat", side_effect=Exception("API Error")):
            res = get_headline_sentiment(["Good news headline"])
            assert res == "NEUTRAL"


@patch("fastapi_app.tasks.alerts.settings")
@patch("httpx.post")
@patch("services.news_aggregator.get_default_aggregator")
@patch("llm.llm_client.get_headline_sentiment")
def test_send_telegram_alert_with_headlines_bullish(
    mock_get_sentiment, mock_get_aggregator, mock_httpx_post, mock_settings
):
    # Setup mocks
    mock_settings.telegram_bot_token = "fake_bot_token"
    mock_settings.telegram_chat_id = "fake_chat_id"

    mock_aggregator = MagicMock()
    mock_aggregator.get_news.return_value = [{"title": "Company wins major contract"}]
    mock_get_aggregator.return_value = mock_aggregator

    mock_get_sentiment.return_value = "BULLISH"

    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_httpx_post.return_value = mock_response

    # Run task
    alert_data = {
        "symbol": "AAPL",
        "price": 150.0,
        "alert_type": "VOLUME_SPIKE",
        "rvol": 2.5,
        "time": "2026-07-17T22:16:06",
    }

    res = send_telegram_alert_task(alert_data)

    # Assertions
    assert res["status"] == "success"
    mock_get_aggregator.assert_called_once()
    mock_aggregator.get_news.assert_called_once_with("AAPL", hours_back=6)
    mock_get_sentiment.assert_called_once_with(["Company wins major contract"])

    # Verify the sent Telegram payload
    mock_httpx_post.assert_called_once()
    post_kwargs = mock_httpx_post.call_args[1]
    assert "json" in post_kwargs
    sent_text = post_kwargs["json"]["text"]
    assert "- *Sentiment:* BULLISH" in sent_text


@patch("fastapi_app.tasks.alerts.settings")
@patch("httpx.post")
@patch("services.news_aggregator.get_default_aggregator")
@patch("llm.llm_client.get_headline_sentiment")
def test_send_telegram_alert_with_headlines_empty(
    mock_get_sentiment, mock_get_aggregator, mock_httpx_post, mock_settings
):
    # Setup mocks
    mock_settings.telegram_bot_token = "fake_bot_token"
    mock_settings.telegram_chat_id = "fake_chat_id"

    mock_aggregator = MagicMock()
    mock_aggregator.get_news.return_value = []
    mock_get_aggregator.return_value = mock_aggregator

    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_httpx_post.return_value = mock_response

    # Run task
    alert_data = {
        "symbol": "AAPL",
        "price": 150.0,
        "alert_type": "VOLUME_SPIKE",
        "rvol": 2.5,
        "time": "2026-07-17T22:16:06",
    }

    res = send_telegram_alert_task(alert_data)

    # Assertions
    assert res["status"] == "success"
    mock_get_aggregator.assert_called_once()
    mock_aggregator.get_news.assert_called_once_with("AAPL", hours_back=6)
    mock_get_sentiment.assert_not_called()

    # Verify the sent Telegram payload
    mock_httpx_post.assert_called_once()
    post_kwargs = mock_httpx_post.call_args[1]
    sent_text = post_kwargs["json"]["text"]
    assert "Sentiment" not in sent_text


@patch("fastapi_app.tasks.alerts.settings")
@patch("httpx.post")
@patch("services.news_aggregator.get_default_aggregator")
@patch("llm.llm_client.get_headline_sentiment")
def test_send_telegram_alert_with_error_robustness(
    mock_get_sentiment, mock_get_aggregator, mock_httpx_post, mock_settings
):
    # Setup mocks
    mock_settings.telegram_bot_token = "fake_bot_token"
    mock_settings.telegram_chat_id = "fake_chat_id"

    # aggregator throws an error
    mock_get_aggregator.side_effect = Exception("Aggregator connection timed out")

    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_httpx_post.return_value = mock_response

    # Run task
    alert_data = {
        "symbol": "AAPL",
        "price": 150.0,
        "alert_type": "VOLUME_SPIKE",
        "rvol": 2.5,
        "time": "2026-07-17T22:16:06",
    }

    # Even if error happens during sentiment, the celery task should succeed and send message
    res = send_telegram_alert_task(alert_data)

    # Assertions
    assert res["status"] == "success"
    mock_get_sentiment.assert_not_called()

    # Verify the sent Telegram payload (no sentiment appended)
    mock_httpx_post.assert_called_once()
    post_kwargs = mock_httpx_post.call_args[1]
    sent_text = post_kwargs["json"]["text"]
    assert "Sentiment" not in sent_text
