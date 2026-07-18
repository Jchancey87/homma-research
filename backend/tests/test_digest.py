import json
from unittest.mock import patch, MagicMock
import pytest
from llm.llm_client import (
    get_catalyst_analysis,
    get_risk_analysis,
    get_deep_context,
    _digest_news,
    _digest_sec
)

@pytest.fixture
def mock_chat():
    with patch("llm.llm_client._chat", return_value="Mocked LLM Response") as mock:
        yield mock

def _extract_json_from_msg(user_msg: str) -> dict:
    start_idx = user_msg.find("{")
    if start_idx != -1:
        try:
            return json.loads(user_msg[start_idx:])
        except Exception:
            pass
    return {}

def test_catalyst_analysis_digestion_skipped(mock_chat):
    # Less than or equal to 2 items
    news = [
        {"title": "News 1", "published": "2026-07-17", "description": "Desc 1"},
        {"title": "News 2", "published": "2026-07-17", "description": "Desc 2"},
    ]
    sec = [
        {"filed": "2026-07-17", "form": "8-K", "primary_doc": "doc1.htm"},
    ]

    data = {
        "event_date": "2026-07-17",
        "news_articles": news,
        "sec_8k_filings": sec,
        "news_freshness": {},
    }

    get_catalyst_analysis("AAPL", data)

    # _chat should be called once (for the main analyst prompt)
    mock_chat.assert_called_once()
    user_msg = mock_chat.call_args[0][1]

    # Verify that the direct JSON serialized strings are in the user message
    payload = _extract_json_from_msg(user_msg)
    assert payload.get("news_articles") == json.dumps(news, default=str)
    assert payload.get("sec_8k_filings") == json.dumps(sec, default=str)

def test_catalyst_analysis_digestion_executed(mock_chat):
    # More than 2 items -> news count 3, sec count 3
    news = [
        {"title": "News 1", "published": "2026-07-17", "description": "Desc 1"},
        {"title": "News 2", "published": "2026-07-17", "description": "Desc 2"},
        {"title": "News 3", "published": "2026-07-17", "description": "Desc 3"},
    ]
    sec = [
        {"filed": "2026-07-17", "form": "8-K", "primary_doc": "doc1.htm"},
        {"filed": "2026-07-17", "form": "8-K", "primary_doc": "doc2.htm"},
        {"filed": "2026-07-17", "form": "8-K", "primary_doc": "doc3.htm"},
    ]

    data = {
        "event_date": "2026-07-17",
        "news_articles": news,
        "sec_8k_filings": sec,
        "news_freshness": {},
    }

    # When digestion is executed, it calls _chat for digestion first, then for main analysis
    # Let's mock _chat return values: first two for digestion, third for main analysis
    mock_chat.side_effect = ["News Digest Result", "SEC Digest Result", "Main Catalyst Analysis Result"]

    get_catalyst_analysis("AAPL", data)

    # 3 calls: 1 news digest, 1 sec digest, 1 catalyst analysis
    assert mock_chat.call_count == 3

    # The calls list
    calls = mock_chat.call_args_list
    # The third call is get_catalyst_analysis call
    final_user_msg = calls[2][0][1]

    # Verify that digests are in the final user message and not the raw news/sec list or raw JSON
    assert "News Digest Result" in final_user_msg
    assert "SEC Digest Result" in final_user_msg
    
    payload = _extract_json_from_msg(final_user_msg)
    assert payload.get("news_articles") == "News Digest Result"
    assert payload.get("sec_8k_filings") == "SEC Digest Result"


def test_risk_analysis_digestion_skipped(mock_chat):
    # Less than or equal to 2 items
    sec_dilution = [
        {"filed": "2026-07-17", "form": "S-3"},
    ]
    sec_toxic = []

    data = {
        "sec_dilution_filings": sec_dilution,
        "sec_toxic_search": sec_toxic,
    }

    get_risk_analysis("AAPL", data)

    mock_chat.assert_called_once()
    user_msg = mock_chat.call_args[0][1]

    payload = _extract_json_from_msg(user_msg)
    assert payload.get("sec_dilution_filings") == json.dumps(sec_dilution, default=str)
    assert payload.get("sec_toxic_search") == json.dumps(sec_toxic, default=str)


def test_risk_analysis_digestion_executed(mock_chat):
    # More than 2 items
    sec_dilution = [
        {"filed": "2026-07-17", "form": "S-3"},
        {"filed": "2026-07-16", "form": "424B5"},
        {"filed": "2026-07-15", "form": "S-3"},
    ]
    sec_toxic = []

    data = {
        "sec_dilution_filings": sec_dilution,
        "sec_toxic_search": sec_toxic,
    }

    mock_chat.side_effect = ["SEC Digest Result", "Main Risk Analysis Result"]

    get_risk_analysis("AAPL", data)

    # 2 calls: 1 for sec_dilution_filings digestion, 1 for main risk analysis
    assert mock_chat.call_count == 2

    final_user_msg = mock_chat.call_args_list[1][0][1]
    assert "SEC Digest Result" in final_user_msg
    
    payload = _extract_json_from_msg(final_user_msg)
    assert payload.get("sec_dilution_filings") == "SEC Digest Result"
    assert payload.get("sec_toxic_search") == json.dumps(sec_toxic, default=str)  # skipped because count is 0 <= 2


def test_deep_context_digestion_skipped(mock_chat):
    data = {
        "news": [],
        "sec_filings": [],
    }

    get_deep_context("AAPL", data)

    mock_chat.assert_called_once()
    user_msg = mock_chat.call_args[0][1]

    payload = _extract_json_from_msg(user_msg)
    assert payload.get("news") == json.dumps([], default=str)
    assert payload.get("sec_filings") == json.dumps([], default=str)


def test_deep_context_digestion_executed(mock_chat):
    news = ["News A", "News B", "News C"]
    data = {
        "news": news,
        "sec_filings": [],
    }

    mock_chat.side_effect = ["News Digest Result", "Main Deep Context Result"]

    get_deep_context("AAPL", data)

    assert mock_chat.call_count == 2
    final_user_msg = mock_chat.call_args_list[1][0][1]
    assert "News Digest Result" in final_user_msg
    
    payload = _extract_json_from_msg(final_user_msg)
    assert payload.get("news") == "News Digest Result"
    assert payload.get("sec_filings") == json.dumps([], default=str)
