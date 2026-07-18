"""
tests/test_news_classifier.py
Unit tests for the keyword-shortcut layer in classify_news_fresh.
All tests are pure Python — zero LLM API calls.
"""
import pytest
from unittest.mock import patch
from llm.llm_client import _keyword_classify, classify_news_fresh


# ---------------------------------------------------------------------------
# _keyword_classify — pure keyword layer (no mocking needed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("headline,expected", [
    # FRESH — FDA/regulatory
    ("FDA approves AAPL drug for rare disease", True),
    ("PDUFA date set for Q3 2026", True),
    ("Company receives CRL from FDA", True),
    ("NDA submission accepted by FDA", True),
    ("Stock cleared by FDA for new indication", True),
    # FRESH — clinical
    ("Phase 3 trial meets primary endpoint", True),
    ("Interim data shows positive results", True),
    ("Top-line results from Phase 2 study", True),
    ("Clinical trial enrollment complete", True),
    # FRESH — corporate events
    ("Company announces merger with rival", True),
    ("Acquisition of XBIO completed", True),
    ("Earnings beat estimates by wide margin", True),
    ("Revenue miss triggers selloff", True),
    ("Licensing deal signed with Pfizer", True),
    # FRESH — capital markets
    ("Announces $50M public offering", True),
    ("Share repurchase program expanded", True),
    ("NASDAQ delisting notice received", True),
    # STALE — analyst commentary
    ("Analyst upgrades AAPL to buy", False),
    ("Price target raised to $200", False),
    ("Firm reiterates overweight rating", False),
    ("Morgan Stanley maintains neutral", False),
    ("Initiates coverage with market perform", False),
    # Ambiguous — returns None (will escalate to LLM)
    ("AAPL trading up 5% on volume", None),
    ("Market rally continues into afternoon", None),
    ("Sector rotation into biotech names", None),
])
def test_keyword_classify(headline, expected):
    assert _keyword_classify(headline) == expected


# ---------------------------------------------------------------------------
# classify_news_fresh — verify LLM is NOT called for resolved headlines
# ---------------------------------------------------------------------------

def test_fresh_headline_skips_llm():
    """FRESH keyword → should return True without touching the LLM."""
    with patch("llm.llm_client._chat") as mock_chat:
        result = classify_news_fresh("FDA approves new cancer drug")
    assert result is True
    mock_chat.assert_not_called()


def test_stale_headline_skips_llm():
    """STALE keyword → should return False without touching the LLM."""
    with patch("llm.llm_client._chat") as mock_chat:
        result = classify_news_fresh("Analyst maintains buy rating on AAPL")
    assert result is False
    mock_chat.assert_not_called()


def test_ambiguous_headline_calls_llm_fresh():
    """Ambiguous headline → LLM is called and result forwarded."""
    with patch("llm.llm_client._chat", return_value="FRESH") as mock_chat, \
         patch("llm.llm_client.Config") as mock_cfg:
        mock_cfg.LLM_API_KEY = "test-key"
        mock_cfg.LLM_MODEL = "test-model"
        mock_cfg.DEEP_LLM_API_KEY = None
        result = classify_news_fresh("Stock surges on unusual volume spike")
    assert result is True
    mock_chat.assert_called_once()


def test_ambiguous_headline_calls_llm_stale():
    """Ambiguous headline → LLM returns STALE."""
    with patch("llm.llm_client._chat", return_value="STALE") as mock_chat, \
         patch("llm.llm_client.Config") as mock_cfg:
        mock_cfg.LLM_API_KEY = "test-key"
        mock_cfg.LLM_MODEL = "test-model"
        mock_cfg.DEEP_LLM_API_KEY = None
        result = classify_news_fresh("Stock surges on unusual volume spike")
    assert result is False
    mock_chat.assert_called_once()


def test_empty_headline_returns_false():
    """Empty/None headline → False immediately, no LLM."""
    with patch("llm.llm_client._chat") as mock_chat:
        assert classify_news_fresh("") is False
        assert classify_news_fresh(None) is False
    mock_chat.assert_not_called()


def test_llm_exception_returns_false():
    """LLM API error on ambiguous headline → graceful False fallback."""
    with patch("llm.llm_client._chat", side_effect=Exception("API down")), \
         patch("llm.llm_client.Config") as mock_cfg:
        mock_cfg.LLM_API_KEY = "test-key"
        mock_cfg.LLM_MODEL = "test-model"
        mock_cfg.DEEP_LLM_API_KEY = None
        result = classify_news_fresh("Stock surges on unusual volume spike")
    assert result is False
