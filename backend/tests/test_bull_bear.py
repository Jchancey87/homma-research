import pytest
from unittest.mock import patch
from llm.llm_client import (
    get_continuation_analysis,
    BULL_SYSTEM,
    BEAR_SYSTEM,
    SYNTHESIS_SYSTEM,
    SINGLE_PASS_SYSTEM,
    REPORT_COMPILER_SYSTEM,
)

def test_continuation_analysis_debate_vs_single_pass():
    # Gainer A: gap_pct = 20.0 (>= 15.0) -> debate loop
    # Gainer B: gap_pct = 10.0 (< 15.0)  -> single-pass
    gainers = [
        {"ticker": "HIGHGAP", "gap_pct": 20.0, "extended_change_pct": 25.0, "float_shares": 5000000.0, "rvol_15m": 6.5, "sector": "Technology", "news_fresh": True, "news_headline": "FDA approval"},
        {"ticker": "LOWGAP", "gap_pct": 10.0, "extended_change_pct": 12.0, "float_shares": 15000000.0, "rvol_15m": 2.1, "sector": "Healthcare", "news_fresh": False, "news_headline": "Analyst upgrade"},
    ]

    def mock_chat_side_effect(system_prompt, user_msg, max_tokens=1024, use_deep_client=False):
        if system_prompt == BULL_SYSTEM:
            return "Bullish points for " + user_msg
        elif system_prompt == BEAR_SYSTEM:
            return "Bearish points for " + user_msg
        elif system_prompt == SYNTHESIS_SYSTEM:
            return "Synthesis report for " + user_msg
        elif system_prompt == SINGLE_PASS_SYSTEM:
            return "Single-pass report for " + user_msg
        elif system_prompt == REPORT_COMPILER_SYSTEM:
            return "Top Picks:\n1. HIGHGAP - thesis\n\nAvoid List:\n- LOWGAP - fade\n\nMarket Context:\nFine tape."
        return "Default response"

    with patch("llm.llm_client._chat", side_effect=mock_chat_side_effect) as mock_chat:
        report, model = get_continuation_analysis(
            date="2026-07-18",
            gainers=gainers,
            archetype_stats=[],
            reflections=[]
        )

        from config import Config
        assert model == Config.DEEP_LLM_MODEL

        assert "Synthesis report" in report
        assert "Single-pass report" in report
        assert "Top Picks:" in report

        calls = mock_chat.call_args_list
        assert len(calls) == 5

        system_prompts_called = [c[0][0] for c in calls]
        assert BULL_SYSTEM in system_prompts_called
        assert BEAR_SYSTEM in system_prompts_called
        assert SYNTHESIS_SYSTEM in system_prompts_called
        assert SINGLE_PASS_SYSTEM in system_prompts_called
        assert REPORT_COMPILER_SYSTEM in system_prompts_called

        for call in calls:
            sys_p = call[0][0]
            user_m = call[0][1]
            deep = call[1].get("use_deep_client", False)

            if sys_p in (BULL_SYSTEM, BEAR_SYSTEM, SYNTHESIS_SYSTEM):
                assert "HIGHGAP" in user_m
                assert "LOWGAP" not in user_m
                if sys_p == SYNTHESIS_SYSTEM:
                    assert deep is True
                else:
                    assert deep is False
            elif sys_p == SINGLE_PASS_SYSTEM:
                assert "LOWGAP" in user_m
                assert "HIGHGAP" not in user_m
                assert deep is True
            elif sys_p == REPORT_COMPILER_SYSTEM:
                assert deep is True
