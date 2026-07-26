"""
Sentiment & Classification Analyzer.

Domain analyzer for headline sentiment, news freshness classification, and pre-digestion.
"""

from typing import List, Optional
from backend.llm.transport import LLMTransport
from backend.llm.prompts import (
    build_headline_sentiment_prompt,
    build_news_freshness_prompt,
    build_pre_digest_prompt,
)


class SentimentAnalyzer:
    """Analyzes sentiment, freshness, and content pre-digestion."""

    def __init__(self, transport: Optional[LLMTransport] = None):
        self.transport = transport or LLMTransport()

    def get_headline_sentiment(self, headlines: List[str]) -> str:
        """Determines sentiment: BULLISH, BEARISH, NEUTRAL, or MIXED."""
        if not headlines:
            return "NEUTRAL"
        sys_p, user_p = build_headline_sentiment_prompt(headlines)
        res = self.transport.chat(user_p, system_prompt=sys_p, model_tier="fast", temperature=0.1)
        res_clean = res.strip().upper()
        if res_clean in ["BULLISH", "BEARISH", "NEUTRAL", "MIXED"]:
            return res_clean
        return "NEUTRAL"

    def classify_news_fresh(self, headline: str, summary: str = "") -> bool:
        """Classifies news as fresh (True) or stale (False)."""
        if not headline:
            return False
        # Fast keyword shortcuts
        h_lower = headline.lower()
        if any(w in h_lower for w in ["fda", "approval", "earnings", "quarter", "acquired", "merger", "patent"]):
            return True

        sys_p, user_p = build_news_freshness_prompt(headline, summary)
        res = self.transport.chat(user_p, system_prompt=sys_p, model_tier="fast", temperature=0.1)
        return "FRESH" in res.upper()

    def get_pre_digest(self, content: str, content_type: str = "news") -> str:
        """Pre-digests raw news/filings content into dense text summary."""
        if not content:
            return ""
        sys_p, user_p = build_pre_digest_prompt(content, content_type)
        return self.transport.chat(user_p, system_prompt=sys_p, model_tier="fast", temperature=0.3)
