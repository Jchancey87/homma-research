"""
Continuation Analyzer.

Domain analyzer for post-market continuation analysis, target-ranked bull/bear debate,
and report compilation.
"""

from typing import Dict, List, Optional, Tuple
from config import Config
from backend.llm.transport import LLMTransport
from backend.llm.prompts import (
    CONTINUATION_SYSTEM,
    BULL_SYSTEM,
    BEAR_SYSTEM,
    SYNTHESIS_SYSTEM,
    SINGLE_PASS_SYSTEM,
    REPORT_COMPILER_SYSTEM,
)


class ContinuationAnalyzer:
    """Analyzes daily gainer continuation potential."""

    def __init__(self, transport: Optional[LLMTransport] = None):
        self.transport = transport or LLMTransport()

    def analyze_gainer_continuation(
        self,
        date: str,
        gainers: List[dict],
        archetype_stats: Optional[List[dict]] = None,
        reflections: Optional[List[dict]] = None
    ) -> Tuple[str, str]:
        """
        Given a date and list of top gainer dicts, returns (report_markdown, model_name).
        For tickers with gap_pct >= 15.0, runs Bull/Bear debate loop.
        """
        if not gainers:
            return "No gainers to analyze.", Config.DEEP_LLM_MODEL

        ticker_reports = []
        for g in gainers:
            gainer_md = (
                f"Ticker: {g['ticker']}\n"
                f"Date: {date}\n"
                f"Price: ${g.get('price', 0):.2f}\n"
                f"Gap %: {g.get('gap_pct', 0):.1f}%\n"
                f"Float: {g.get('float_shares', 0) / 1e6:.1f}M\n"
                f"RVOL: {g.get('rvol', 0):.1f}x\n"
                f"Sector: {g.get('sector', 'Unknown')}\n"
                f"News / Catalyst: {g.get('news_title', 'No news')}\n"
                f"Fresh Catalyst: {g.get('news_fresh', False)}\n"
            )

            gap_pct = g.get('gap_pct', 0) or 0.0
            if gap_pct >= 15.0:
                bull_case = self.transport.chat(gainer_md, system_prompt=BULL_SYSTEM, model_tier="fast")
                bear_case = self.transport.chat(gainer_md, system_prompt=BEAR_SYSTEM, model_tier="fast")
                debate_prompt = f"{gainer_md}\nBull Case:\n{bull_case}\n\nBear Case:\n{bear_case}\n"
                ticker_md = self.transport.chat(debate_prompt, system_prompt=SYNTHESIS_SYSTEM, model_tier="deep")
            else:
                ticker_md = self.transport.chat(gainer_md, system_prompt=SINGLE_PASS_SYSTEM, model_tier="deep")

            ticker_reports.append(ticker_md)

        combined_tickers_md = "\n\n".join(ticker_reports)
        summary_md = self.transport.chat(combined_tickers_md, system_prompt=REPORT_COMPILER_SYSTEM, model_tier="deep")
        final_report = f"# Daily Continuation Analysis Report — {date}\n\n{combined_tickers_md}\n\n{summary_md}"

        return final_report, Config.DEEP_LLM_MODEL
