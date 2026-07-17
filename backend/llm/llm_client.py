"""
LLM client — OpenAI-compatible SDK pointed at Groq (or any provider).
Swap provider by changing LLM_BASE_URL + LLM_API_KEY + LLM_MODEL in .env.
No other code changes required.
"""
from openai import OpenAI
from config import Config
from validation import EASTERN_TZ

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

def _get_client() -> OpenAI:
    return OpenAI(
        api_key=Config.LLM_API_KEY,
        base_url=Config.LLM_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/jchancey87/Analysis-App",
            "X-Title": "Trading Journal Analysis App",
        }
    )

def _get_deep_client() -> OpenAI:
    return OpenAI(
        api_key=Config.DEEP_LLM_API_KEY,
        base_url=Config.DEEP_LLM_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/jchancey87/Analysis-App",
            "X-Title": "Trading Journal Analysis App",
        }
    )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

CONTINUATION_SYSTEM = """\
You are a post-market analyst for a small-cap day trader focused on gap-and-go setups.
Your job is to produce a structured nightly continuation report based on that day's top gainers.

The trader's historical data shows these patterns work best for continuation:
- Float < 10M with RVOL > 5x: highest continuation rate
- Fresh catalyst (news_fresh=True): +30% more likely to hold overnight
- Gap > 30% on volume > 10x average: strong momentum signal
- Healthcare/Biotech sector on FDA/trial news: binary catalyst, beware fade risk
- Gap-and-hold (steady price action, no sharp reversal after open): continuation signal
- Gap-and-fade (sharp selloff within 30 min of open): avoid next day

For each ticker, output the following exact structure:

### [TICKER] — [Continuation Rating: 🟢 HIGH / 🟡 MEDIUM / 🔴 LOW / ⚫ AVOID]

| Field | Value |
|---|---|
| Gap % | X.X% |
| Float | X.XM |
| RVOL | Xx |
| Sector | ... |
| Catalyst | Fresh / Stale / Unknown |

**Thesis**: [2–3 sentences: why this rating, what to watch for]
**Key Risk**: [1 sentence]
**Watch Level**: [price level to watch at open, or "N/A"]

---

End the report with:

## 🏆 Top Picks for Continuation Watch
Ranked list of the top 3 tickers with the strongest case, and one sentence each.

## ⚠️ Avoid List
Any tickers that are likely to fade or have high risk, with one reason each.

## Market Context
One paragraph summarizing the overall tape quality for the day based on these names.

Be direct and concise. No filler. No disclaimers. This is a private trading tool.
"""

SENTIMENT_SYSTEM = """\
You are a trading journal analyst.
You answer questions about market conditions and setup quality grounded in the user's own journal data.
Only reference patterns present in the provided archetype stats. Do not add generic market commentary.
Be direct, concise, and quantitative where possible.
"""

DEEP_ANALYSIS_SYSTEM = """\
You are a senior quantitative and technical analyst producing a deep-dive report on the top daily gainers.
You will receive technicals (SMAs, RSI) and fundamental data (cash, earnings, insiders).

Format each stock as:

### [TICKER] — Deep Analysis
**Technicals**:
- [RSI/SMA breakdown]
- [Price action / Volume profile]
**Hard Catalyst & Event Risk**:
- [Earnings dates/status, breaking news]
**Dilution & Structure**:
- [Cash position vs Net Income burn rate implications]
- [Float/Shares Out structure]
**Insider Sentiment**:
- [Insider buying/selling activity over last 90d]
**Continuation Thesis**:
- [Bull case for tomorrow]
- [Bear case / Fade risk]

Conclude the report with a brief summary of what to watch for tomorrow. Keep it professional, insightful, and concise. No fluff.
"""

NEWS_FRESH_SYSTEM = """\
You classify stock news headlines as FRESH or STALE.
FRESH = catalyst is new today (earnings beat/miss, FDA approval/rejection, contract win, merger, clinical trial result, regulatory approval).
STALE = recycled news, no new catalyst, general sector hype, price target updates, analyst upgrades without new data.
Reply with exactly one word: FRESH or STALE.\
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_continuation_analysis(date: str, gainers: list[dict],
                               archetype_stats: list[dict] | None = None) -> tuple[str, str]:
    """
    Given a date and list of top-10 gainer dicts, return a markdown continuation report.
    Optionally grounds the report in historical archetype_stats from the journal.
    Returns (report_text, model_name).
    """
    rows_md = "\n".join(
        f"- **{g['ticker']}**: change={g.get('extended_change_pct', '?')}%, gap={g.get('gap_pct', '?')}%, "
        f"float={_fmt_float(g.get('float_shares'))}, "
        f"rvol={g.get('rvol_15m', '?')}x, "
        f"sector={g.get('sector', '?')}, "
        f"open=${g.get('open_price', '?')}, close=${g.get('close_price', '?')}, "
        f"news_fresh={g.get('news_fresh', '?')}, "
        f"headline: {g.get('news_headline') or 'N/A'}"
        for g in gainers
    )

    # Add historical grounding if we have archetype data
    history_context = ""
    if archetype_stats:
        history_context = "\n\nHistorical archetype stats from this trader's journal:\n" + "\n".join(
            f"- {s['tag']}: {s['count']} trades, "
            f"avg_gap={s.get('avg_gap_pct')}%, "
            f"avg_rvol={s.get('avg_rvol')}x, "
            f"avg_cleanliness={s.get('avg_cleanliness')}/10"
            for s in (archetype_stats or [])
        )

    user_msg = (
        f"Date: {date}\n\n"
        f"Today's top gainers (sorted by extended day change %):\n{rows_md}"
        f"{history_context}\n\n"
        "Produce the full nightly continuation report now."
    )

    result = _chat(CONTINUATION_SYSTEM, user_msg, max_tokens=2048)
    return result, Config.LLM_MODEL



def get_sentiment_analysis(query: str, archetype_stats: list[dict]) -> tuple[str, str]:
    """
    Answer a free-form research query grounded in the user's archetype stats.
    Returns (response_text, model_name).
    """
    stats_md = "\n".join(
        f"- {s['tags']}: count={s.get('count')}, "
        f"avg_gap={s.get('avg_gap_pct')}%, "
        f"avg_clean={s.get('avg_cleanliness')}"
        for s in archetype_stats
    ) or "No archetype data yet."

    user_msg = (
        f"Journal archetype stats:\n{stats_md}\n\n"
        f"User question: {query}"
    )

    result = _chat(SENTIMENT_SYSTEM, user_msg)
    return result, Config.LLM_MODEL


def get_deep_analysis_report(date: str, deep_data: list[dict]) -> tuple[str, str]:
    """
    Given detailed technical and fundamental data for the top 3 gainers,
    returns a comprehensive deep analysis report.
    Returns (report_text, model_name).
    """
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


def classify_news_fresh(headline: str) -> bool:
    """
    Returns True if the headline is classified as FRESH catalyst.
    Falls back to False on API error.
    """
    if not headline or not Config.LLM_API_KEY:
        return False
    try:
        result = _chat(NEWS_FRESH_SYSTEM, f"Headline: {headline}", max_tokens=5)
        return result.strip().upper().startswith('FRESH')
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chat(system: str, user: str, max_tokens: int = 1024, use_deep_client: bool = False) -> str:
    if use_deep_client and Config.DEEP_LLM_API_KEY:
        client = _get_deep_client()
        model = Config.DEEP_LLM_MODEL
    else:
        client = _get_client()
        model = Config.LLM_MODEL

    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system',  'content': system},
            {'role': 'user',    'content': user},
        ],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _fmt_float(shares) -> str:
    if shares is None:
        return '?'
    m = shares / 1e6
    return f"{m:.1f}M"


DEEP_RESEARCH_SYSTEM = """
You are a senior Equity Research Analyst specializing in high-volatility small-cap stocks. 
Your goal is to provide a comprehensive "Deep Dive" using the provided raw data (from FMP and yfinance).

CRITICAL DATA HANDLING:
1. **Fundamental Health**: Look at `fundamentals`. Access `income_statement` for EPS/Revenue trends. Check `cash_position` (FMP) specifically for liquidity vs burn.
2. **Ownership & Dilution**: Check `insider_activity` for net buying/selling. Check `institutional` for big money positioning. Look at `profile` for Float vs Shares Outstanding.
3. **Corporate Actions**: Analyze `recent_actions` for splits/dividends. If a reverse split is detected, highlight the ratio and its implications.
4. **Catalysts**: Scrutinize `news_headlines` (both FMP and yfinance). Check `earnings_calendar` for the NEXT confirmed date. If it's in the past, note that the report hasn't caught the next cycle yet.
5. **Analyst Context**: Use `analyst_estimates` to compare current performance against market expectations.

Structure your report with:
- **Executive Summary & Verdict** (Bull/Bear/Neutral)
- **The Data (Fundamentals & Ownership)** (Explicitly mention Cash, Net Income, Float, and Insider activity)
- **Recent Catalysts & News Analysis** (Synthesize headlines into a coherent story)
- **Risks & Red Flags** (Dilution risk, toxic financing, or structural weakness)
- **Conclusion & Potential Action**

Tone: Professional, clinical, and data-backed. Avoid generic fluff. If data is present, USE IT. If data is truly null, state that the specific metric is unavailable.
"""


def get_ticker_deep_research(ticker: str, data: dict) -> tuple[str, str]:
    """Perform a deep research analysis using gathered yfinance data."""
    import json
    from datetime import datetime
    today_str = datetime.now(EASTERN_TZ).strftime('%Y-%m-%d')
    user_msg = (
        f"Today's Date: {today_str}\n"
        f"Ticker: {ticker}\n"
        f"Data Snapshot:\n{json.dumps(data, indent=2)}"
    )
    result = _chat(DEEP_RESEARCH_SYSTEM, user_msg, max_tokens=3000, use_deep_client=True)
    return result, Config.DEEP_LLM_MODEL


# ---------------------------------------------------------------------------
# Risk Detection
# ---------------------------------------------------------------------------

RISK_DETECTION_SYSTEM = """\
You are a forensic equity analyst specializing in structural risk identification for small-cap and micro-cap stocks.
You are given raw data from SEC filings, short interest data, insider transactions, and corporate actions.

Your job is to produce a structured Risk Report that a day trader can act on immediately.
Classify each risk factor as: 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW / ⚪ N/A.
Be direct. Do not hedge. Do not add disclaimers.

Output EXACTLY this format:

## 🚨 Risk Report: [TICKER]
### Overall Risk Score: [1–10] (10 = most dangerous)

| Risk Factor | Status | Severity | Detail |
|---|---|---|---|
| Reverse Split History | [Yes/No + dates] | 🔴/🟡/🟢 | [ratio, how recent] |
| Active Shelf Registration (S-3) | [Yes/No + date] | 🔴/🟡/🟢 | [amount if known] |
| Recent ATM/424B Offering | [Yes/No + date] | 🔴/🟡/🟢 | [proceeds if known] |
| Toxic Financing Detected | [Yes/No] | 🔴/🟡/🟢 | [filing type, keyword matched] |
| Short % of Float | [X%] | 🔴/🟡/🟢 | [>20%=high, 10-20%=medium] |
| Days to Cover | [X days] | 🔴/🟡/🟢 | [>10=squeeze trap risk] |
| Insider Activity (90d) | [Net buy/sell shares] | 🔴/🟡/🟢 | [brief summary] |
| Cash Position | [$X or Unknown] | 🔴/🟡/🟢 | [runway concern if <6mo] |
| Share Dilution Trend | [Flat/Increasing/Unknown] | 🔴/🟡/🟢 | [recent share count change] |

### 🧠 Risk Summary
[2–3 sentences: overall verdict, which risks are most actionable, what the trader should watch]

### ⚡ Immediate Action
[One sentence: what this means RIGHT NOW for a trader considering this stock]
"""


def get_risk_analysis(ticker: str, data: dict) -> tuple[str, str]:
    """Produce a structured Risk Detection report from gathered risk signals."""
    import json
    user_msg = (
        f"Ticker: {ticker}\n\n"
        f"Risk Signal Data:\n{json.dumps(data, indent=2, default=str)}"
    )
    result = _chat(RISK_DETECTION_SYSTEM, user_msg, max_tokens=2000)
    return result, Config.LLM_MODEL


# ---------------------------------------------------------------------------
# Catalyst Analysis
# ---------------------------------------------------------------------------

CATALYST_ANALYSIS_SYSTEM = """\
You are a catalyst quality analyst for a momentum day trader focused on small-cap gap stocks.
Your job: determine whether this ticker's recent price move has a real, durable catalyst or is likely to fade.

You are given:
  - news_articles: headlines with 'days_from_event' (negative = before event, 0 = event day, positive = after)
  - news_freshness: per-headline classification (FRESH = within 2 days of event, RECENT = within 7 days, STALE = older)
  - sec_8k_filings: 8-K filings with parsed 'catalyst_items' (item codes like 1.01, 8.01) and 'keyword_hits'
  - sec_fulltext_hits: EDGAR full-text search results for catalyst keywords
  - earnings_calendar: next earnings date and EPS estimates
  - analyst_activity: recent upgrades/downgrades

IMPORTANT: freshness is evaluated relative to event_date, NOT today.
A headline published on or up to 2 days before the event date is FRESH regardless of how long ago that was.
An 8-K filed on or near the event date with item 8.01 (FDA/other) or 2.02 (earnings) is a strong primary catalyst signal.

Classify the catalyst as:
🟢 TIER 1 — Binary event with clear resolution (FDA approval/rejection, earnings surprise, acquisition, clinical trial result)
🟡 TIER 2 — Soft catalyst (contract win, partnership, MOU, analyst upgrade with new data, guidance raise)
🔴 TIER 3 — No real catalyst (vague press release, general sector hype, price target update, no filing, unknown)

Output EXACTLY this format (ensure tables have proper newlines to render correctly):

## ⚡ Catalyst Report: [TICKER]
### Catalyst Tier: [🟢 TIER 1 / 🟡 TIER 2 / 🔴 TIER 3]

| Field | Value |
|---|---|
| Primary Catalyst | [headline or SEC filing description, or "None identified"] |
| Catalyst Date | [YYYY-MM-DD or "Unknown"] |
| Catalyst Freshness | [FRESH / RECENT / STALE / UNKNOWN — relative to event_date] |
| Catalyst Type | [FDA / Earnings / Contract / Partnership / Clinical Trial / Other / None] |
| SEC Filing Signal | [8-K item code + description if present, else "None"] |
| Expected Duration | [Intraday / 1–3 days / Multi-week / Binary] |
| Next Earnings Date | [date or "Unknown"] |

### 📰 News & Filing Summary
[Bullet points: 3–5 most relevant items. For each, include the source (Polygon/yfinance/SEC), published date, and days_from_event if available.]

### 🔬 Catalyst Quality Assessment
[2–3 sentences: Why this tier? Is there an SEC filing that confirms the narrative? Is the catalyst specific and verifiable?]

### ⚠️ Risk to Catalyst Thesis
[1–2 sentences: What could invalidate or reverse the narrative?]
"""


def get_catalyst_analysis(ticker: str, data: dict) -> tuple[str, str]:
    """Produce a structured Catalyst Analysis report from gathered news and filing data."""
    import json

    # Build a concise summary section the LLM can reason about
    event_date   = data.get('event_date', 'unknown')
    fresh_counts = {}
    for label in data.get('news_freshness', {}).values():
        fresh_counts[label] = fresh_counts.get(label, 0) + 1

    freshness_summary = ', '.join(f'{v}× {k}' for k, v in sorted(fresh_counts.items()))

    # Surface 8-K catalyst signals prominently
    catalyst_8k_signals = []
    for f in data.get('sec_8k_filings', []):
        if f.get('catalyst_items') or f.get('keyword_hits'):
            catalyst_8k_signals.append({
                'filed':           f['filed'],
                'days_from_event': f.get('days_from_event'),
                'catalyst_items':  f.get('catalyst_items', []),
                'keyword_hits':    f.get('keyword_hits', []),
            })

    user_msg = (
        f"Ticker: {ticker}\n"
        f"Event Date: {event_date}\n"
        f"News freshness summary (relative to event date): {freshness_summary or 'no articles found'}\n"
        f"8-K filings with catalyst signals: {len(catalyst_8k_signals)} found\n\n"
        f"Full Catalyst Signal Data:\n{json.dumps(data, indent=2, default=str)}"
    )

    result = _chat(CATALYST_ANALYSIS_SYSTEM, user_msg, max_tokens=2000)
    return result, Config.LLM_MODEL



# ---------------------------------------------------------------------------
# Deep Context
# ---------------------------------------------------------------------------

DEEP_CONTEXT_SYSTEM = """\
You are a quantitative setup scorer for a small-cap momentum trader.
You receive multi-timeframe technical data, float structure, relative strength vs SPY,
options sentiment, and the stock's own historical gainer appearances from a personal trading journal.

Your job: synthesize everything into a unified Setup Score and actionable playbook.
The trader wants to know: IS THIS A REAL SETUP or noise?

Output EXACTLY this format (ensure tables have proper newlines to render correctly):

## 📊 Deep Context: [TICKER]
### Setup Score: [1–10] | Conviction: [LOW / MEDIUM / HIGH]

**Technical Picture**:

| Indicator | Value | Signal |
|---|---|---|
| Price vs SMA 20 | [above/below by X%] | 🟢/🔴 |
| Price vs SMA 50 | [above/below by X%] | 🟢/🔴 |
| Price vs SMA 200 | [above/below by X%] | 🟢/🔴 |
| 52-Week Range Position | [X% of range] | 🟢/🟡/🔴 |
| RS vs SPY (20d) | [X.Xx] | 🟢/🔴 |
| Options Sentiment | [FEAR / GREED / NEUTRAL] | 🔴/🟢/⚪ |

**Float & Structure**:
- Float: [XM shares]
- Float Rotation: [X days at avg volume]
- Shares trend: [diluting / stable / unknown]

**Journal History** ([N] prior appearances):
[Bullet: most recent gap events for this ticker from the journal, with dates and gap %, max 5]

**The Playbook**:
| Scenario | Trigger | Target | Stop |
|---|---|---|---|
| Bull case | [specific trigger] | [+X% or price level] | [stop condition] |
| Bear case | [specific trigger] | [fade target] | [invalidation] |

### 🎯 Bottom Line
[1–2 sentences. Be direct. Is this worth trading? What's the edge?]
"""


def get_deep_context(ticker: str, data: dict) -> tuple[str, str]:
    """Produce a structured Deep Context report from technical, structural, and historical data."""
    import json
    user_msg = (
        f"Ticker: {ticker}\n\n"
        f"Context Data:\n{json.dumps(data, indent=2, default=str)}"
    )
    result = _chat(DEEP_CONTEXT_SYSTEM, user_msg, max_tokens=2500)
    return result, Config.LLM_MODEL


# ---------------------------------------------------------------------------
# PIPE Analysis
# ---------------------------------------------------------------------------

PIPE_ANALYSIS_SYSTEM = """\
You are a forensic equity analyst specializing in private placement (PIPE) deal structure
for small-cap and micro-cap stocks. You are given SEC 8-K filing data, parsed PIPE terms,
shares dilution history, and historical PIPE frequency for a ticker.

Your job: classify the deal and produce a structured PIPE report a momentum day trader
can act on in seconds. Be direct. No hedging. No disclaimers.

Classify the deal as:
🟢 FAVORABLE — Fixed-price equity/preferred, reputable investor, growth use of proceeds, no toxic terms
🟡 MIXED     — Some positive signals offset by red flags; situational
🔴 TOXIC     — Variable/floating conversion, death-spiral structure, known toxic patterns

Output EXACTLY this format:

## 📋 PIPE Analysis: [TICKER]
### Deal Classification: [🟢 FAVORABLE / 🟡 MIXED / 🔴 TOXIC]

| Field | Value |
|---|---|
| Security Type | [Common Stock / Preferred / Convertible Note / Warrant / Unknown] |
| Pricing | [Fixed at $X.XX / Variable — describe formula / Unknown] |
| Gross Proceeds | [$X.XM or Unknown] |
| Investor Type | [Named strategic / Institutional / Unknown / Known toxic lender pattern] |
| Use of Proceeds | [Specific growth use / Generic working capital / Refinancing old debt] |
| Issuer PIPE History | [First PIPE / Serial issuer — N prior raises] |
| Toxic Signals | [None / List matched terms] |
| Deal Score | [1–5 where 5=most favorable] |
| Filing Date | [YYYY-MM-DD] |
| 8-K Items | [1.01 / 3.02 / both] |

### 📊 Structure Analysis
[2–3 sentences: fixed vs variable pricing, security type implications, dilution math if proceeds known]

### ⚡ Trading Implication
[1–2 sentences: what this means RIGHT NOW for a momentum trader. Does this support or undermine the move?]

### ⚠️ Key Risk to Thesis
[1 sentence: the single most important risk from this filing]
"""


def get_pipe_analysis(ticker: str, data: dict) -> tuple[str, str]:
    """Produce a structured PIPE Analysis report from the pipe_service payload."""
    import json
    user_msg = (
        f"Ticker: {ticker}\n\n"
        f"PIPE Signal Data:\n{json.dumps(data, indent=2, default=str)}"
    )
    result = _chat(PIPE_ANALYSIS_SYSTEM, user_msg, max_tokens=1500)
    return result, Config.LLM_MODEL


# ---------------------------------------------------------------------------
# Watchlist Enrichment
# ---------------------------------------------------------------------------

WATCHLIST_ENRICHMENT_SYSTEM = """
You are a trading assistant. You are given a stock ticker, its sector, and a brief description.
Your job is to provide:
1. A concise, one-sentence "Note" that summarizes the core business or recent momentum profile (max 15 words).
2. A list of 2-3 relevant "Tags" from this list: [momentum, breakout, reversal, squeeze, catalyst, earnings, watchonly].

Respond ONLY with valid JSON in this format:
{
  "notes": "Short summary here...",
  "tags": ["tag1", "tag2"]
}
"""

def get_ticker_enrichment(ticker: str, sector: str, description: str) -> dict:
    """Get AI-generated notes and tags for a watchlist ticker."""
    import json
    user_msg = (
        f"Ticker: {ticker}\n"
        f"Sector: {sector}\n"
        f"Description: {description}\n"
    )
    try:
        # Use OpenRouter (deep client) to avoid Groq rate limits on quick tasks
        raw = _chat(WATCHLIST_ENRICHMENT_SYSTEM, user_msg, max_tokens=150, use_deep_client=True)
        # Strip potential markdown fences
        clean = raw.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(clean)
    except Exception as e:
        import logging
        import traceback
        log = logging.getLogger(__name__)
        log.warning(f"Watchlist enrichment failed for {ticker}: {str(e)}")
        # log.debug(traceback.format_exc()) # Optional: very verbose
        return {"notes": None, "tags": []}


# ---------------------------------------------------------------------------
# Biotech Catalyst Extraction
# ---------------------------------------------------------------------------

BIOTECH_CATALYST_SYSTEM = """
You are a biotech equity research assistant. You are given news headlines and SEC filings full-text search results for a stock ticker.
Your job is to identify the single most significant upcoming trial readout, FDA decision, PDUFA date, or clinical milestone.
Extract:
1. The upcoming catalyst description (concise, max 20 words).
2. The estimated catalyst date (must be formatted as YYYY-MM-DD if a specific date is given, or null if unknown or only a broad range like "Q4 2026" or "mid-2026" is given).

Respond ONLY with valid JSON in this format:
{
  "upcoming_catalyst": "Concise description of the catalyst",
  "catalyst_date": "YYYY-MM-DD or null"
}
"""

def get_upcoming_catalyst(ticker: str, news: list[dict], sec_filings: list[dict]) -> dict:
    """Extract biotech upcoming trials/milestones using LLM."""
    import json
    data_payload = {
        "news": news,
        "sec_filings": sec_filings
    }
    user_msg = (
        f"Ticker: {ticker}\n"
        f"Data: {json.dumps(data_payload, default=str)}\n"
    )
    try:
        raw = _chat(BIOTECH_CATALYST_SYSTEM, user_msg, max_tokens=250, use_deep_client=True)
        clean = raw.strip().replace('```json', '').replace('```', '').strip()
        parsed = json.loads(clean)
        # Ensure correct keys and defaults
        return {
            "upcoming_catalyst": parsed.get("upcoming_catalyst") or None,
            "catalyst_date": parsed.get("catalyst_date") or None
        }
    except Exception as e:
        import logging
        log = logging.getLogger(__name__)
        log.warning(f"Catalyst extraction failed for {ticker}: {e}")
        return {"upcoming_catalyst": None, "catalyst_date": None}

