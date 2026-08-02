"""
LLM Client Facade.

Maintains 100% backward compatibility with all existing jobs, tasks, and routers while
delegating transport, prompts, and analysis to decoupled sub-modules:
- backend.llm.transport (LLMTransport)
- backend.llm.prompts (Prompt builder functions & string constants)
- backend.llm.analyzers.* (Domain analyzer classes)
"""

import copy
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from config import Config
from backend.llm.transport import LLMTransport
from backend.llm.prompts import (
    CONTINUATION_SYSTEM,
    BULL_SYSTEM,
    BEAR_SYSTEM,
    SYNTHESIS_SYSTEM,
    SINGLE_PASS_SYSTEM,
    REPORT_COMPILER_SYSTEM,
    SENTIMENT_SYSTEM,
    DEEP_ANALYSIS_SYSTEM,
    NEWS_FRESH_SYSTEM,
    HEADLINE_SENTIMENT_SYSTEM,
    NEWS_DIGEST_SYSTEM,
    SEC_DIGEST_SYSTEM,
    RISK_DETECTION_SYSTEM,
    CATALYST_ANALYSIS_SYSTEM,
    DAILY_RUNDOWN_SYSTEM,
)

from backend.llm.analyzers.continuation_analyzer import ContinuationAnalyzer
from backend.llm.analyzers.sentiment_analyzer import SentimentAnalyzer
from backend.llm.analyzers.reflection_analyzer import ReflectionAnalyzer

logger = logging.getLogger(__name__)

# Default transport instance
default_transport = LLMTransport()

# Instantiated default analyzers
continuation_analyzer = ContinuationAnalyzer(default_transport)
sentiment_analyzer = SentimentAnalyzer(default_transport)
reflection_analyzer = ReflectionAnalyzer(default_transport)

_FRESH_KEYWORDS = {
    # FDA / regulatory
    "fda", "pdufa", "nda", "bla", "anda", "sba", "510k", "510(k)",
    "approval", "approved", "approv", "cleared", "clearance",
    "rejection", "rejected", "complete response letter", "crl",
    "breakthrough therapy", "fast track", "priority review",
    "accelerated approval", "orphan drug",
    # Clinical
    "phase 1", "phase 2", "phase 3", "phase i", "phase ii", "phase iii",
    "clinical trial", "trial results", "primary endpoint", "endpoint met",
    "endpoint missed", "data readout", "interim data", "topline",
    "top-line", "positive data", "negative data",
    # Corporate events
    "earnings", "eps", "revenue beat", "revenue miss", "guidance",
    "merger", "acquisition", "acquired", "buyout", "takeover",
    "tender offer", "going private", "strategic review",
    "licensing deal", "partnership", "collaboration agreement",
    "contract award", "government contract",
    # Capital markets
    "offering", "public offering", "private placement", "dilution",
    "share repurchase", "buyback", "dividend", "spinoff", "spin-off",
    # Legal / regulatory
    "sec investigation", "doj", "subpoena", "settlement", "lawsuit",
    "indictment", "delisting", "nasdaq notice",
}

_STALE_KEYWORDS = {
    "price target", "pt raised", "pt lowered", "analyst upgrade",
    "analyst downgrade", "maintains", "reiterates", "overweight",
    "underweight", "neutral", "buy rating", "sell rating",
    "sector perform", "market perform", "initiates coverage",
    "sees upside", "top pick",
}


def _fmt_float(shares: Any) -> str:
    if shares is None:
        return '?'
    try:
        m = float(shares) / 1e6
        return f"{m:.1f}M"
    except (ValueError, TypeError):
        return '?'


def _chat(
    system: str,
    user: str,
    max_tokens: int = 1024,
    use_deep_client: bool = False
) -> str:
    """Internal transport bridge preserving backward compatibility for unit tests patching `llm_client._chat`."""
    tier = "deep" if use_deep_client else "fast"
    return default_transport.chat(
        prompt=user,
        system_prompt=system,
        model_tier=tier,
        max_tokens=max_tokens
    )


def _keyword_classify(headline: str) -> Optional[bool]:
    if not headline:
        return None
    h = headline.lower()
    for kw in _FRESH_KEYWORDS:
        if kw in h:
            return True
    for kw in _STALE_KEYWORDS:
        if kw in h:
            return False
    return None


def _digest_news(news: list) -> str:
    if not news:
        return "No news to digest."
    formatted = []
    for item in news:
        if isinstance(item, dict):
            title = item.get("title") or "N/A"
            pub = item.get("published") or "N/A"
            desc = item.get("description") or ""
            source = item.get("source") or "N/A"
            days = item.get("days_from_event")
            days_str = f" ({days} days from event)" if days is not None else ""
            desc_part = f"\n  Description: {desc[:200]}" if desc else ""
            formatted.append(f"- [{source}] {pub}{days_str}: {title}{desc_part}")
        else:
            formatted.append(f"- {str(item)}")

    user_msg = "News articles to digest:\n" + "\n".join(formatted)
    try:
        return _chat(NEWS_DIGEST_SYSTEM, user_msg, max_tokens=1000)
    except Exception as e:
        logger.warning(f"Failed to digest news: {e}")
        return "Error digesting news."


def _digest_sec(sec_filings: list) -> str:
    if not sec_filings:
        return "No SEC filings to digest."
    formatted = []
    for item in sec_filings:
        if isinstance(item, dict):
            form = item.get("form") or item.get("form_type") or "Filing"
            filed = item.get("filed") or item.get("filing_date") or "N/A"
            days = item.get("days_from_event")
            days_str = f" ({days} days from event)" if days is not None else ""
            doc = item.get("primary_doc") or item.get("description") or "N/A"
            items = item.get("catalyst_items") or []
            items_str = ", ".join(f"{it.get('code')}: {it.get('description')}" for it in items) if isinstance(items, list) else str(items)
            hits = item.get("keyword_hits") or []
            hits_str = ", ".join(hits) if isinstance(hits, list) else str(hits)
            formatted.append(
                f"- Form {form} filed on {filed}{days_str} (Doc: {doc}):\n"
                f"  Catalyst Items: {items_str or 'None'}\n"
                f"  Keyword Hits: {hits_str or 'None'}"
            )
        else:
            formatted.append(f"- {str(item)}")

    user_msg = "SEC Filings to digest:\n" + "\n".join(formatted)
    try:
        return _chat(SEC_DIGEST_SYSTEM, user_msg, max_tokens=1000)
    except Exception as e:
        logger.warning(f"Failed to digest SEC filings: {e}")
        return "Error digesting SEC filings."


def _process_data_digestion(data: dict) -> dict:
    data_copy = copy.deepcopy(data)

    for k in ('news_articles', 'news'):
        news = data_copy.get(k)
        if news is not None and isinstance(news, list):
            if len(news) > 2:
                data_copy[k] = _digest_news(news)
            else:
                data_copy[k] = json.dumps(news, default=str)

    sec_keys = ('sec_8k_filings', 'sec_fulltext_hits', 'sec_dilution_filings', 'sec_toxic_search', 'sec_filings')
    for k in sec_keys:
        filings = data_copy.get(k)
        if filings is not None and isinstance(filings, list):
            if len(filings) > 2:
                data_copy[k] = _digest_sec(filings)
            else:
                data_copy[k] = json.dumps(filings, default=str)

    return data_copy


def _run_debate(gainer_md: str, history_context: str = "", reflections_context: str = "") -> str:
    bull_user_msg = f"{reflections_context}\n{gainer_md}\n{history_context}\nGenerate the bull case."
    bull_case = _chat(BULL_SYSTEM, bull_user_msg, max_tokens=500, use_deep_client=False)
    bear_user_msg = f"{reflections_context}\n{gainer_md}\n{history_context}\nGenerate the bear case."
    bear_case = _chat(BEAR_SYSTEM, bear_user_msg, max_tokens=500, use_deep_client=False)
    synthesis_user_msg = f"{reflections_context}\n{gainer_md}\nBull Case:\n{bull_case}\n\nBear Case:\n{bear_case}\n"
    return _chat(SYNTHESIS_SYSTEM, synthesis_user_msg, max_tokens=600, use_deep_client=True)


def get_continuation_analysis(
    date: str,
    gainers: List[dict],
    archetype_stats: Optional[List[dict]] = None,
    reflections: Optional[List[dict]] = None
) -> Tuple[str, str]:
    if not gainers:
        return "No gainers to analyze.", Config.DEEP_LLM_MODEL

    history_context = ""
    if archetype_stats:
        history_context = "\n\nHistorical archetype stats from this trader's journal:\n" + "\n".join(
            f"- {s['tag']}: {s['count']} trades, "
            f"avg_gap={s.get('avg_gap_pct')}%, "
            f"avg_rvol={s.get('avg_rvol')}x, "
            f"avg_cleanliness={s.get('avg_cleanliness')}/10"
            for s in (archetype_stats or [])
        )

    reflections_context = ""
    if reflections:
        reflections_context = "### Recent Post-Market Reflections & Lessons Learned:\n"
        for r in reflections:
            lessons = r.get("lessons_json") or {}
            avoid_sec = ", ".join(lessons.get("avoid_sectors", [])) or "None"
            max_fl = lessons.get("max_float")
            fmt_max_fl = f"{max_fl / 1e6:.1f}M" if max_fl else "None"
            reflections_context += (
                f"- **Date: {r['date']}**:\n"
                f"  - Sectors to Avoid: {avoid_sec}\n"
                f"  - Max Float Constraint: {fmt_max_fl}\n"
                f"  - Details: {r['reflection_text']}\n"
            )
        reflections_context += "\nKeep these lessons and constraints in mind when rating today's picks.\n\n"

    ticker_reports = []
    for g in gainers:
        gainer_md = (
            f"Ticker: {g['ticker']}\n"
            f"Date: {date}\n"
            f"Change: {g.get('extended_change_pct', '?')}%\n"
            f"Gap: {g.get('gap_pct', '?')}%\n"
            f"Float: {_fmt_float(g.get('float_shares'))}\n"
            f"RVOL: {g.get('rvol_15m', '?')}x\n"
            f"Sector: {g.get('sector', '?')}\n"
            f"Open: ${g.get('open_price', '?')}\n"
            f"Close: ${g.get('close_price', '?')}\n"
            f"News Fresh: {g.get('news_fresh', '?')}\n"
            f"News Headline: {g.get('news_headline') or 'N/A'}"
        )
        try:
            gap_val = float(g.get('gap_pct') or 0)
        except (ValueError, TypeError):
            gap_val = 0.0

        if gap_val >= 15.0:
            bull_user_msg = f"{reflections_context}\n{gainer_md}\n{history_context}\nGenerate the bull case."
            bull_case = _chat(BULL_SYSTEM, bull_user_msg, max_tokens=500, use_deep_client=False)

            bear_user_msg = f"{reflections_context}\n{gainer_md}\n{history_context}\nGenerate the bear case."
            bear_case = _chat(BEAR_SYSTEM, bear_user_msg, max_tokens=500, use_deep_client=False)

            synthesis_user_msg = (
                f"{reflections_context}\n"
                f"{gainer_md}\n"
                f"Bull Case:\n{bull_case}\n\n"
                f"Bear Case:\n{bear_case}\n\n"
                f"Synthesize the bull and bear arguments into the final section."
            )
            ticker_md = _chat(SYNTHESIS_SYSTEM, synthesis_user_msg, max_tokens=600, use_deep_client=True)
        else:
            single_user_msg = f"{reflections_context}\n{gainer_md}\n{history_context}\nAnalyze continuation potential."
            ticker_md = _chat(SINGLE_PASS_SYSTEM, single_user_msg, max_tokens=600, use_deep_client=True)

        ticker_reports.append(ticker_md)

    combined_tickers_md = "\n\n".join(ticker_reports)
    summary_user_msg = f"Individual ticker reports:\n\n{combined_tickers_md}"
    summary_md = _chat(REPORT_COMPILER_SYSTEM, summary_user_msg, max_tokens=800, use_deep_client=True)
    report_text = f"# Daily Continuation Analysis Report — {date}\n\n{combined_tickers_md}\n\n{summary_md}"

    return report_text, Config.DEEP_LLM_MODEL


def get_headline_sentiment(headlines: List[str]) -> str:
    if not headlines:
        return "NEUTRAL"
    if not Config.LLM_API_KEY:
        return "NEUTRAL"
    try:
        user_msg = "\n".join(f"- {h}" for h in headlines)
        result = _chat(HEADLINE_SENTIMENT_SYSTEM, user_msg, max_tokens=10)
        sentiment = result.strip().upper()
        for possible in ["BULLISH", "BEARISH", "NEUTRAL", "MIXED"]:
            if possible in sentiment:
                return possible
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"


def classify_news_fresh(headline: str) -> bool:
    if not headline:
        return False
    shortcut = _keyword_classify(headline)
    if shortcut is not None:
        return shortcut
    if not Config.LLM_API_KEY:
        return False
    try:
        result = _chat(NEWS_FRESH_SYSTEM, f"Headline: {headline}", max_tokens=5)
        return result.strip().upper().startswith('FRESH')
    except Exception:
        return False


def get_pre_digest(content: str, content_type: str = "news") -> str:
    return sentiment_analyzer.get_pre_digest(content, content_type)


def get_reflection(picks_data: List[dict]) -> Tuple[str, dict]:
    return reflection_analyzer.get_reflection(picks_data)


def get_sentiment_analysis(query: str, archetype_stats: List[dict]) -> Tuple[str, str]:
    stats_summary = "\n".join(
        f"- {s['tag']}: {s['count']} trades, avg_gap={s.get('avg_gap_pct')}%, avg_rvol={s.get('avg_rvol')}x"
        for s in archetype_stats
    )
    user_prompt = f"Archetype Data:\n{stats_summary}\n\nUser Question: {query}"
    text = _chat(SENTIMENT_SYSTEM, user_prompt, max_tokens=500, use_deep_client=False)
    return text, Config.LLM_MODEL


def get_deep_analysis_report(date: str, deep_data: List[dict]) -> Tuple[str, str]:
    rows_md = ""
    for g in deep_data:
        rows_md += f"\n- **{g['ticker']}**:\n"
        for k, v in g.items():
            if k != 'ticker':
                rows_md += f"  - {k}: {v}\n"

    user_msg = (
        f"Date: {date}\n\n"
        f"Detailed Data for Top 3 Gainers:\n{rows_md}\n"
        "Produce the deep technical and fundamental analysis report now."
    )
    result = _chat(DEEP_ANALYSIS_SYSTEM, user_msg, max_tokens=2500, use_deep_client=True)
    return result, Config.DEEP_LLM_MODEL


def get_ticker_deep_research(ticker: str, data: dict) -> Tuple[str, str]:
    from datetime import datetime
    from validation import EASTERN_TZ
    today_str = datetime.now(EASTERN_TZ).strftime('%Y-%m-%d')
    user_msg = (
        f"Today's Date: {today_str}\n"
        f"Ticker: {ticker}\n"
        f"Data Snapshot:\n{json.dumps(data, indent=2)}"
    )
    result = _chat(DEEP_ANALYSIS_SYSTEM, user_msg, max_tokens=3000, use_deep_client=True)
    return result, Config.DEEP_LLM_MODEL


def get_risk_analysis(ticker: str, data: dict) -> Tuple[str, str]:
    digested_data = _process_data_digestion(data)
    user_msg = (
        f"Ticker: {ticker}\n\n"
        f"Risk Signal Data:\n{json.dumps(digested_data, indent=2, default=str)}"
    )
    result = _chat(RISK_DETECTION_SYSTEM, user_msg, max_tokens=2000)
    return result, Config.LLM_MODEL


def get_catalyst_analysis(ticker: str, data: dict) -> Tuple[str, str]:
    event_date = data.get('event_date', 'unknown')
    fresh_counts = {}
    for label in data.get('news_freshness', {}).values():
        fresh_counts[label] = fresh_counts.get(label, 0) + 1

    freshness_summary = ', '.join(f'{v}× {k}' for k, v in sorted(fresh_counts.items()))

    catalyst_8k_signals = []
    for f in data.get('sec_8k_filings', []):
        if isinstance(f, dict) and (f.get('catalyst_items') or f.get('keyword_hits')):
            catalyst_8k_signals.append({
                'filed':           f.get('filed'),
                'days_from_event': f.get('days_from_event'),
                'catalyst_items':  f.get('catalyst_items', []),
                'keyword_hits':    f.get('keyword_hits', []),
            })

    digested_data = _process_data_digestion(data)
    user_msg = (
        f"Ticker: {ticker}\n"
        f"Event Date: {event_date}\n"
        f"News freshness summary (relative to event date): {freshness_summary or 'no articles found'}\n"
        f"8-K filings with catalyst signals: {len(catalyst_8k_signals)} found\n\n"
        f"Full Catalyst Signal Data:\n{json.dumps(digested_data, indent=2, default=str)}"
    )
    result = _chat(CATALYST_ANALYSIS_SYSTEM, user_msg, max_tokens=2000)
    return result, Config.LLM_MODEL



def get_deep_context(ticker: str, data: dict) -> Tuple[str, str]:
    digested_data = _process_data_digestion(data)
    user_msg = (
        f"Ticker: {ticker}\n\n"
        f"Context Payload:\n{json.dumps(digested_data, indent=2, default=str)}"
    )
    result = _chat(DEEP_ANALYSIS_SYSTEM, user_msg, max_tokens=2500, use_deep_client=True)
    return result, Config.DEEP_LLM_MODEL


def get_pipe_analysis(ticker: str, data: dict) -> Tuple[str, str]:
    user_msg = (
        f"Ticker: {ticker}\n\n"
        f"PIPE Deal Data:\n{json.dumps(data, indent=2, default=str)}"
    )
    result = _chat("Analyze PIPE deal toxicity.", user_msg, max_tokens=1500)
    return result, Config.LLM_MODEL


def get_ticker_enrichment(ticker: str, context: dict) -> dict:
    prompt_body = f"Ticker: {ticker}\nContext: {context}\nReturn JSON with keys 'notes' and 'tags'."
    text = _chat("Generate ticker enrichment JSON.", prompt_body, max_tokens=500, use_deep_client=False)
    return {"notes": text, "tags": [ticker]}


def get_upcoming_catalyst(ticker: str, context: dict) -> dict:
    prompt_body = f"Ticker: {ticker}\nContext: {context}\nReturn JSON with keys 'upcoming_catalyst' and 'catalyst_date'."
    text = _chat("Extract upcoming catalyst event date.", prompt_body, max_tokens=500, use_deep_client=False)
    return {"upcoming_catalyst": text, "catalyst_date": "N/A"}


def get_daily_rundown(date_str: str, market_data: dict, raw_email_text: Optional[str] = None) -> Tuple[str, str]:
    """
    Generate structured Daily Market Rundown from aggregated market feeds, top gainers,
    calendar events, news, and optional morning research email text.
    """
    email_section = f"\n\n--- Morning Research Email Text ---\n{raw_email_text}" if raw_email_text else ""
    user_msg = (
        f"Target Date: {date_str}\n\n"
        f"Aggregated Market Data:\n{json.dumps(market_data, indent=2, default=str)}"
        f"{email_section}\n\n"
        "Generate the complete Daily Market Rundown in exact Markdown format."
    )
    result = _chat(DAILY_RUNDOWN_SYSTEM, user_msg, max_tokens=3000, use_deep_client=True)
    return result, Config.DEEP_LLM_MODEL

