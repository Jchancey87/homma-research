"""
catalyst_service.py — Data gatherer for the Catalyst Analysis feature.

Aggregates signals from:
  - Polygon.io: recent news headlines anchored to event date
  - yfinance: news headlines (free fallback / supplementary)
  - SEC EDGAR: 8-K filings with item code parsing (FDA, earnings, contracts)
  - SEC EDGAR: full-text search for catalyst keywords near event date
  - yfinance: upcoming earnings calendar, analyst upgrades/downgrades
"""
import logging
import requests
from datetime import datetime, timedelta
from config import Config

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
        import pytz
        date = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')

    polygon_news = _get_polygon_news(ticker, date)
    yf_news      = _get_yfinance_news(ticker, date)

    # Merge: polygon first, then yfinance, de-duplicate by title prefix
    seen_titles = {a['title'][:40].lower() for a in polygon_news}
    for article in yf_news:
        if article['title'][:40].lower() not in seen_titles:
            polygon_news.append(article)
            seen_titles.add(article['title'][:40].lower())

    all_news = polygon_news[:20]  # cap at 20 combined

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

def _get_polygon_news(ticker: str, anchor_date: str, n: int = 15) -> list[dict]:
    """
    Fetch news from Polygon.io anchored ±14 days around anchor_date.
    Returns list with 'title', 'published', 'publisher', 'description'.
    """
    if not Config.POLYGON_API_KEY:
        log.warning('[Catalyst] POLYGON_API_KEY not set, skipping Polygon news.')
        return []

    try:
        dt        = datetime.strptime(anchor_date, '%Y-%m-%d')
        from_date = (dt - timedelta(days=14)).strftime('%Y-%m-%d')
        to_date   = (dt + timedelta(days=1)).strftime('%Y-%m-%d')

        resp = requests.get(
            'https://api.polygon.io/v2/reference/news',
            params={
                'ticker':              ticker,
                'published_utc.gte':   from_date,
                'published_utc.lte':   to_date,
                'order':               'desc',
                'limit':               n,
                'apiKey':              Config.POLYGON_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()

        return [
            {
                'source':      'polygon',
                'title':       a.get('title', ''),
                'published':   a.get('published_utc', '')[:10],
                'publisher':   a.get('publisher', {}).get('name', ''),
                'description': (a.get('description') or '')[:400],
                'days_from_event': _days_from_event(a.get('published_utc', '')[:10], anchor_date),
            }
            for a in resp.json().get('results', [])
        ]
    except Exception as e:
        log.warning(f'[Catalyst] Polygon news fetch failed: {e}')
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
    """Return the upcoming earnings date and EPS estimates from yfinance."""
    try:
        import yfinance as yf
        t   = yf.Ticker(ticker)
        cal = t.calendar
        if isinstance(cal, dict):
            return {k: str(v) for k, v in cal.items()}
        elif hasattr(cal, 'to_dict'):
            result = {}
            for col in cal.columns:
                for idx in cal.index:
                    result[f'{col}_{idx}'] = str(cal.at[idx, col])
            return result
        return {}
    except Exception as e:
        log.warning(f'[Catalyst] Earnings calendar fetch failed: {e}')
        return {}


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
