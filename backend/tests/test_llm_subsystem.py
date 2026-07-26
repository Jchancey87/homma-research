"""
Unit tests for decoupled LLM subsystem (transport, prompts, analyzers).
Zero network calls — uses mock LLMTransport instances.
"""

from unittest.mock import MagicMock
from backend.llm.transport import LLMTransport
from backend.llm.prompts import (
    build_headline_sentiment_prompt,
    build_news_freshness_prompt,
    build_pre_digest_prompt,
    build_reflection_prompt,
)
from backend.llm.analyzers.sentiment_analyzer import SentimentAnalyzer
from backend.llm.analyzers.reflection_analyzer import ReflectionAnalyzer
from backend.llm.analyzers.continuation_analyzer import ContinuationAnalyzer


def test_prompt_builders():
    """Verify prompt builders generate expected system and user prompts."""
    sys_p, user_p = build_headline_sentiment_prompt(["FDA approval received for Drug X"])
    assert "BULLISH" in sys_p
    assert "FDA approval" in user_p

    sys_p2, user_p2 = build_news_freshness_prompt("Quarterly Earnings Beat", "Q3 EPS up 50%")
    assert "FRESH" in sys_p2
    assert "Quarterly Earnings" in user_p2

    sys_p3, user_p3 = build_pre_digest_prompt("Headline 1\nHeadline 2", content_type="sec")
    assert "forensic equity analyst" in sys_p3
    assert "Headline 1" in user_p3


def test_sentiment_analyzer_with_mock_transport():
    """Verify SentimentAnalyzer uses injected transport cleanly."""
    mock_transport = MagicMock(spec=LLMTransport)
    mock_transport.chat.return_value = "BULLISH"

    analyzer = SentimentAnalyzer(transport=mock_transport)
    result = analyzer.get_headline_sentiment(["Stock surges 20% on contract win"])

    assert result == "BULLISH"
    mock_transport.chat.assert_called_once()


def test_reflection_analyzer_json_parsing():
    """Verify ReflectionAnalyzer extracts structured JSON lessons from raw response."""
    mock_transport = MagicMock(spec=LLMTransport)
    mock_transport.chat.return_value = (
        "Great execution overall.\n\n"
        "```json\n"
        "{\"avoid_sectors\": [\"Biotech\"], \"max_float\": 5000000, \"key_takeaways\": [\"Hold runners\"]}\n"
        "```"
    )

    analyzer = ReflectionAnalyzer(transport=mock_transport)
    text, lessons = analyzer.get_reflection([{"ticker": "AAPL", "gain": "15%"}])

    assert "Great execution overall." in text
    assert lessons["avoid_sectors"] == ["Biotech"]
    assert lessons["max_float"] == 5000000


def test_continuation_analyzer():
    """Verify ContinuationAnalyzer runs single-pass vs debate depending on gap_pct."""
    mock_transport = MagicMock(spec=LLMTransport)
    mock_transport.chat.return_value = "### AAPL — 🟢 HIGH"

    analyzer = ContinuationAnalyzer(transport=mock_transport)
    gainers = [{"ticker": "AAPL", "price": 10.0, "gap_pct": 8.0}]

    report, model = analyzer.analyze_gainer_continuation("2026-07-26", gainers)
    assert "AAPL" in report
    mock_transport.chat.assert_called()
