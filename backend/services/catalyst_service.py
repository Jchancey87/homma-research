"""
catalyst_service.py — Data gatherer for the Catalyst Analysis feature.

Aggregates signals from:
  - Massive.com (fka Polygon.io): recent news headlines anchored to event date
  - yfinance: news headlines (free fallback / supplementary)
  - SEC EDGAR: 8-K filings with item code parsing (FDA, earnings, contracts)
  - SEC EDGAR: full-text search for catalyst keywords near event date
  - yfinance: upcoming earnings calendar, analyst upgrades/downgrades
"""
import logging
import requests
from datetime import datetime, timedelta
from config import Config
from validation import EASTERN_TZ

log = logging.getLogger(__name__)

# 8-K item codes that indicate real catalysts
_8K_CATALYST_ITEMS = {
    '1.01': 'Material Definitive Agreement (contract/deal)',
    '1.02': 'Termination of Material Agreement',
    '1.05': 'Material Cybersecurity Incident',
    '2.02': 'Results of Operations (earnings)',
    '2.05': 'Costs Associated with Exit/Disposal',
    '2.06': 'Material Impairments',
    '3.01': 'Notice of Delisting',
    '5.02': 'Departure/Appointment of Director/Officer',
    '7.01': 'Regulation FD Disclosure (guidance/PR)',
    '8.01': 'Other Events (FDA, clinical trial, misc catalyst)',
    '9.01': 'Financial Statements and Exhibits',
}

# Keywords that strongly suggest a real catalyst in a filing
_CATALYST_KEYWORDS = [
    'FDA', 'approval', 'approved', 'phase', 'clinical trial', 'PDUFA',
    'NDA', 'BLA', 'IND', 'earnings', 'revenue', 'EPS', 'guidance',
    'contract', 'agreement', 'partnership', 'acquisition', 'merger',
    'licensing', 'grant', 'award', 'milestone',
]


def build_catalyst_payload(ticker: str, date: str | None = None) -> dict:
    """
    Gather all signals needed for a Catalyst Analysis LLM report.

    Args:
        ticker: Stock ticker symbol.
        date:   The date of the gainer event (YYYY-MM-DD). Used to anchor
                all freshness scoring relative to the event, not to today.
                Defaults to today if not provided.

    Returns:
        Structured dict for the LLM prompt.
    """
    if not date:
        date = datetime.now(EASTERN_TZ).strftime('%Y-%m-%d')

    fmp_news = _get_fmp_news(ticker, date)
    yf_news      = _get_yfinance_news(ticker, date)

    # Merge: fmp first, then yfinance, de-duplicate by title prefix
    seen_titles = {a['title'][:40].lower() for a in fmp_news}
    for article in yf_news:
        if article['title'][:40].lower() not in seen_titles:
            fmp_news.append(article)
            seen_titles.add(article['title'][:40].lower())

    all_news = fmp_news[:20]  # cap at 20 combined

    sec_8k      = _get_sec_8k_filings_parsed(ticker, date)
    sec_fts     = _get_sec_fulltext_catalyst(ticker, date)

    payload = {
        'ticker':             ticker,
        'event_date':         date,
        'news_articles':      all_news,
        'news_freshness':     _score_news_freshness_relative(all_news, date),
        'sec_8k_filings':     sec_8k,
        'sec_fulltext_hits':  sec_fts,
        'earnings_calendar':  _get_earnings_calendar(ticker),
        'analyst_activity':   _get_analyst_activity(ticker),
    }
    return payload


# ---------------------------------------------------------------------------
# News collectors
# ---------------------------------------------------------------------------

def _get_fmp_news(ticker: str, anchor_date: str, n: int = 15) -> list[dict]:
    """
    Fetch news from Financial Modeling Prep (FMP) anchored ±14 days around anchor_date.
    Returns list with 'source', 'title', 'published', 'publisher', 'description', 'days_from_event'.
    """
    try:
        from services.fmp_service import get_stock_news
        from datetime import datetime, timezone, timedelta

        anchor_dt = datetime.strptime(anchor_date, '%Y-%m-%d')
        from_date = anchor_dt - timedelta(days=14)
        to_date   = anchor_dt + timedelta(days=2)

        articles = get_stock_news(ticker, limit=40)
        if not articles:
            return []

        results = []
        for a in articles:
            pub_str = a.get('date', '')
            pub_dt = None
            if pub_str:
                try:
                    pub_dt = datetime.strptime(pub_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        pub_dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00')).replace(tzinfo=None)
                    except ValueError:
                        pass

            if pub_dt:
                if pub_dt < from_date or pub_dt > to_date:
                    continue

            pub_date_str = pub_dt.strftime('%Y-%m-%d') if pub_dt else (pub_str[:10] if pub_str else '')
            description = a.get('text', '') or ''
            results.append({
                'source':          'fmp',
                'title':           a.get('title', '') or '',
                'published':       pub_date_str,
                'publisher':       a.get('site', '') or 'FMP',
                'description':     description[:400],
                'days_from_event': _days_from_event(pub_date_str, anchor_date),
            })

        return results[:n]
    except Exception as e:
        log.warning(f'[Catalyst] FMP news fetch failed: {e}')
        return []


def _get_yfinance_news(ticker: str, anchor_date: str, n: int = 10) -> list[dict]:
    """
    Fetch news from yfinance as a free fallback/supplement.
    Handles both old (providerPublishTime int) and new (content.pubDate str) API shapes.
    Filters to articles within ±14 days of anchor_date.
    """
    try:
        import yfinance as yf
        from datetime import timezone

        anchor_dt = datetime.strptime(anchor_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)

        t    = yf.Ticker(ticker)
        news = t.news or []

        results = []
        for item in news[:40]:
            # --- Title extraction ---
            title = (
                item.get('title') or
                (item.get('content') or {}).get('title', '') or
                ''
            )
            if not title:
                continue

            # --- Publisher extraction ---
            publisher = (
                item.get('publisher') or
                (item.get('content') or {}).get('provider', {}).get('displayName', '') or
                ''
            )

            # --- Timestamp extraction (multiple shapes) ---
            pub_dt  = None
            pub_str = ''

            # Shape 1: providerPublishTime (unix int)
            ts = item.get('providerPublishTime')
            if ts and isinstance(ts, (int, float)) and ts > 1_000_000:
                pub_dt = datetime.fromtimestamp(ts, tz=timezone.utc)

            # Shape 2: content.pubDate (ISO string "2025-11-14T...")
            if pub_dt is None:
                pub_date_str = (item.get('content') or {}).get('pubDate', '')
                if pub_date_str:
                    try:
                        pub_dt = datetime.fromisoformat(
                            pub_date_str.replace('Z', '+00:00')
                        ).astimezone(timezone.utc)
                    except ValueError:
                        pass

            # Shape 3: displayTime (ISO string)
            if pub_dt is None:
                display_time = item.get('displayTime', '')
                if display_time:
                    try:
                        pub_dt = datetime.fromisoformat(
                            display_time.replace('Z', '+00:00')
                        ).astimezone(timezone.utc)
                    except ValueError:
                        pass

            if pub_dt:
                pub_str   = pub_dt.strftime('%Y-%m-%d')
                days_diff = (pub_dt - anchor_dt).days
                if abs(days_diff) > 14:
                    continue
            else:
                pub_str   = ''
                days_diff = None

            results.append({
                'source':          'yfinance',
                'title':           title,
                'published':       pub_str,
                'publisher':       publisher,
                'description':     '',
                'days_from_event': days_diff,
            })

            if len(results) >= n:
                break

        return results
    except Exception as e:
        log.warning(f'[Catalyst] yfinance news fetch failed: {e}')
        return []


# ---------------------------------------------------------------------------
# SEC signal collectors
# ---------------------------------------------------------------------------

def _get_sec_8k_filings_parsed(ticker: str, anchor_date: str, days_back: int = 60) -> list[dict]:
    """
    Fetch 8-K filings and parse item codes + keyword signals from description.
    Returns enriched list with catalyst_items and keyword_hits fields.
    """
    try:
        from services.sec_service import get_cik_from_ticker, _SUBMISSIONS_URL, _HEADERS, _sleep
        import time

        cik = get_cik_from_ticker(ticker)
        if not cik:
            return []

        dt      = datetime.strptime(anchor_date, '%Y-%m-%d')
        cutoff  = dt - timedelta(days=days_back)
        ceiling = dt + timedelta(days=2)  # include filings filed day-of or day-after event

        _sleep()
        resp = requests.get(_SUBMISSIONS_URL.format(cik=cik), headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        recent      = data.get('filings', {}).get('recent', {})
        form_types  = recent.get('form', [])
        filed_dates = recent.get('filingDate', [])
        descriptions= recent.get('primaryDocument', [])
        accessions  = recent.get('accessionNumber', [])
        items_list  = recent.get('items', [])  # 8-K item codes field

        results = []
        for form, filed, desc, acc, items_raw in zip(
            form_types, filed_dates, descriptions, accessions, items_list
        ):
            if not form.upper().startswith('8-K'):
                continue
            try:
                filed_dt = datetime.strptime(filed, '%Y-%m-%d')
            except ValueError:
                continue
            if filed_dt < cutoff or filed_dt > ceiling:
                continue

            # Parse item codes from the items field (comma-separated string like "1.01,8.01")
            raw_items = str(items_raw or '').replace(';', ',').split(',')
            parsed_items = []
            for code in raw_items:
                code = code.strip()
                if code in _8K_CATALYST_ITEMS:
                    parsed_items.append({
                        'code':        code,
                        'description': _8K_CATALYST_ITEMS[code],
                    })

            # Keyword scan on description filename (often contains keywords)
            desc_lower = (desc or '').lower()
            kw_hits = [kw for kw in _CATALYST_KEYWORDS if kw.lower() in desc_lower]

            acc_clean = acc.replace('-', '')
            url = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{desc}'

            days_diff = (filed_dt - dt).days

            results.append({
                'form':            form,
                'filed':           filed,
                'days_from_event': days_diff,
                'primary_doc':     desc,
                'catalyst_items':  parsed_items,
                'keyword_hits':    kw_hits,
                'url':             url,
            })

            if len(results) >= 15:
                break

        return results
    except Exception as e:
        log.warning(f'[Catalyst] SEC 8-K parsed fetch failed: {e}')
        return []


def _get_sec_fulltext_catalyst(ticker: str, anchor_date: str) -> list[dict]:
    """
    Full-text search SEC EDGAR for catalyst keywords near the event date.
    Uses EFTS to find 8-K/PR filings mentioning key catalyst terms.
    """
    try:
        from services.sec_service import search_filings_text
        keywords = ['FDA', 'approval', 'clinical trial', 'earnings', 'contract', 'partnership']
        return search_filings_text(ticker, keywords, days_back=30, n=8)
    except Exception as e:
        log.warning(f'[Catalyst] SEC full-text search failed: {e}')
        return []


# ---------------------------------------------------------------------------
# Earnings & analyst
# ---------------------------------------------------------------------------

def _get_earnings_calendar(ticker: str) -> dict:
    """Return the upcoming earnings date and EPS estimates.

    Priority:
      1. Financial Modeling Prep (FMP) — confirmed dates from SEC filings
      2. yfinance — scraper fallback, all dates annotated as past/upcoming

    Both paths stamp '_data_as_of' and '_source' so the LLM always knows
    how fresh the data is and whether a reported date is truly future.
    """
    # --- Primary: FMP ---
    try:
        from services.fmp_service import get_earnings_calendar as fmp_calendar
        result = fmp_calendar(ticker)
        if result.get('_source') == 'fmp':
            log.debug(f'[Catalyst] Earnings calendar via FMP for {ticker}')
            return result
    except Exception as e:
        log.warning(f'[Catalyst] FMP earnings calendar failed: {e}')

    # --- Fallback: yfinance (with staleness annotation) ---
    try:
        import yfinance as yf
        today = datetime.now(EASTERN_TZ).date()

        t   = yf.Ticker(ticker)
        cal = t.calendar
        raw: dict = {}
        if isinstance(cal, dict):
            raw = {k: str(v) for k, v in cal.items()}
        elif hasattr(cal, 'to_dict'):
            for col in cal.columns:
                for idx in cal.index:
                    raw[f'{col}_{idx}'] = str(cal.at[idx, col])

        # Annotate every date value so the LLM knows past vs. upcoming
        annotated = {}
        for k, v in raw.items():
            annotated[k] = v
            for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
                try:
                    parsed = datetime.strptime(v[:10], '%Y-%m-%d').date()
                    annotated[f'{k}_status'] = (
                        'upcoming' if parsed >= today else 'PAST — already occurred'
                    )
                    break
                except ValueError:
                    continue

        annotated['_source']      = 'yfinance_fallback'
        annotated['_data_as_of']  = str(today)
        annotated['_reliability'] = 'LOW — yfinance scraper; dates may be stale'
        return annotated
    except Exception as e:
        log.warning(f'[Catalyst] yfinance earnings fallback failed: {e}')
        return {'_source': 'unavailable'}


def _get_analyst_activity(ticker: str, n: int = 8) -> list[dict]:
    """Return recent analyst upgrades/downgrades from yfinance."""
    try:
        import yfinance as yf
        t  = yf.Ticker(ticker)
        df = t.upgrades_downgrades
        if df is None or df.empty:
            return []
        df = df.sort_index(ascending=False).head(n)
        return df.reset_index().to_dict(orient='records')
    except Exception as e:
        log.warning(f'[Catalyst] Analyst activity fetch failed: {e}')
        return []


# ---------------------------------------------------------------------------
# Date-relative freshness scoring
# ---------------------------------------------------------------------------

def _days_from_event(pub_date: str, anchor_date: str) -> int | None:
    """Return signed days between publish date and event date (negative = before event)."""
    try:
        pub = datetime.strptime(pub_date[:10], '%Y-%m-%d')
        anc = datetime.strptime(anchor_date, '%Y-%m-%d')
        return (pub - anc).days
    except Exception:
        return None


def _score_news_freshness_relative(articles: list[dict], anchor_date: str) -> dict:
    """
    Score each headline's freshness relative to anchor_date (not today).
    FRESH  = published within 2 days before or on the event date.
    RECENT = published within 7 days before event.
    STALE  = older than 7 days before event, or no date.

    Does NOT call the LLM (avoids misclassification due to time shift).
    """
    scores = {}
    for article in articles:
        title = article.get('title', '')[:80]
        if not title:
            continue
        days = article.get('days_from_event')
        if days is None:
            scores[title] = 'UNKNOWN'
        elif -2 <= days <= 1:
            scores[title] = 'FRESH'
        elif -7 <= days < -2:
            scores[title] = 'RECENT'
        else:
            scores[title] = 'STALE'
    return scores
