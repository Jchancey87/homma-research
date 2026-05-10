"""
sec_service.py — Shared SEC EDGAR data fetcher.

Uses the public EDGAR APIs (no key required, just a User-Agent header):
  - Submissions API: https://data.sec.gov/submissions/CIK{cik}.json
  - EFTS full-text search: https://efts.sec.gov/LATEST/search-index?q=...
  - Company facts: https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json

Rate limit: 10 requests/second per SEC policy.
"""
import time
import logging
import requests
from datetime import datetime, timedelta
from pydantic import TypeAdapter, ValidationError
from config import Config
from validation.external_schemas import SECEFTSSource, SECCompanyFactShare

log = logging.getLogger(__name__)

_HEADERS = {'User-Agent': Config.SEC_USER_AGENT, 'Accept-Encoding': 'gzip, deflate'}
_TICKER_TO_CIK_URL = 'https://www.sec.gov/files/company_tickers.json'
_SUBMISSIONS_URL   = 'https://data.sec.gov/submissions/CIK{cik}.json'
_FACTS_URL         = 'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
_EFTS_URL          = 'https://efts.sec.gov/LATEST/search-index'

# Module-level CIK cache to avoid repeated lookups in a single process lifetime
_cik_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# CIK Resolution
# ---------------------------------------------------------------------------

def get_cik_from_ticker(ticker: str) -> str | None:
    """Resolve a ticker to its zero-padded 10-digit CIK. Returns None if not found."""
    ticker = ticker.upper()
    if ticker in _cik_cache:
        return _cik_cache[ticker]

    try:
        resp = requests.get(_TICKER_TO_CIK_URL, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for entry in data.values():
            if entry.get('ticker', '').upper() == ticker:
                cik = str(entry['cik_str']).zfill(10)
                _cik_cache[ticker] = cik
                return cik
    except Exception as e:
        log.warning(f'[SEC] CIK lookup failed for {ticker}: {e}')
    return None


# ---------------------------------------------------------------------------
# Filings (Submissions API)
# ---------------------------------------------------------------------------

def get_recent_filings(ticker: str, forms: list[str] | None = None,
                       days_back: int = 180, n: int = 20) -> list[dict]:
    """
    Return recent SEC filings for a ticker, filtered by form type.

    Args:
        ticker:    Stock ticker symbol.
        forms:     List of form types to include (e.g. ['S-3', '8-K', '424B3']).
                   If None, returns all form types.
        days_back: How far back to search (default 180 days).
        n:         Max number of filings to return.

    Returns:
        List of dicts: {form, filed, description, accession_number, url}
    """
    forms = [f.upper() for f in (forms or [])]
    cik = get_cik_from_ticker(ticker)
    if not cik:
        log.warning(f'[SEC] No CIK for {ticker}')
        return []

    cutoff = datetime.utcnow() - timedelta(days=days_back)

    try:
        _sleep()
        resp = requests.get(_SUBMISSIONS_URL.format(cik=cik), headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f'[SEC] Submissions fetch failed for {ticker}: {e}')
        return []

    recent = data.get('filings', {}).get('recent', {})
    form_types   = recent.get('form', [])
    filed_dates  = recent.get('filingDate', [])
    descriptions = recent.get('primaryDocument', [])
    accessions   = recent.get('accessionNumber', [])

    results = []
    for form, filed, desc, acc in zip(form_types, filed_dates, descriptions, accessions):
        try:
            filed_dt = datetime.strptime(filed, '%Y-%m-%d')
        except ValueError:
            continue

        if filed_dt < cutoff:
            continue
        if forms and not any(form.upper().startswith(f) for f in forms):
            continue

        acc_clean = acc.replace('-', '')
        url = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{desc}'
        results.append({
            'form':             form,
            'filed':            filed,
            'description':      desc,
            'accession_number': acc,
            'url':              url,
        })

        if len(results) >= n:
            break

    return results


# ---------------------------------------------------------------------------
# EFTS Full-Text Search
# ---------------------------------------------------------------------------

def search_filings_text(ticker: str, keywords: list[str],
                        days_back: int = 60, n: int = 10) -> list[dict]:
    """
    Search SEC EDGAR full-text for a ticker + keywords (e.g. toxic financing terms).

    Returns list of dicts: {entity_name, file_date, form_type, description, url}
    """
    query = f'"{ticker}" ' + ' '.join(f'"{k}"' for k in keywords)
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    params = {
        'q':        query,
        'dateRange': 'custom',
        'startdt':  cutoff,
        'forms':    '8-K,S-3,424B3,S-1',
        '_source':  'file_date,entity_name,form_type,display_names,file_num',
        'hits.hits.total.value': n,
    }

    try:
        _sleep()
        resp = requests.get(_EFTS_URL, headers=_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get('hits', {}).get('hits', [])
    except Exception as e:
        log.warning(f'[SEC EFTS] Search failed ({query[:60]}): {e}')
        return []

    results = []
    for hit in hits[:n]:
        raw_src = hit.get('_source', {})
        try:
            src = SECEFTSSource.model_validate(raw_src)
        except ValidationError:
            # Malformed hit — skip rather than crash
            continue
        results.append({
            'entity_name': src.entity_name or '',
            'file_date':   src.file_date or '',
            'form_type':   src.form_type or '',
            'description': (src.display_names[0] if src.display_names else ''),
        })
    return results


# ---------------------------------------------------------------------------
# Company Facts (XBRL — shares outstanding trend)
# ---------------------------------------------------------------------------

def get_shares_history(ticker: str, n_periods: int = 8) -> list[dict]:
    """
    Return common shares outstanding from SEC XBRL company facts.
    Useful for detecting dilution trends over recent quarters.

    Returns list of dicts: {end_date, shares, form}
    """
    cik = get_cik_from_ticker(ticker)
    if not cik:
        return []

    try:
        _sleep()
        resp = requests.get(_FACTS_URL.format(cik=cik), headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        facts = resp.json()
    except Exception as e:
        log.warning(f'[SEC] Company facts fetch failed for {ticker}: {e}')
        return []

    # CommonStockSharesOutstanding is the most reliable field
    us_gaap = facts.get('facts', {}).get('us-gaap', {})
    shares_data = (
        us_gaap.get('CommonStockSharesOutstanding', {}) or
        us_gaap.get('SharesOutstanding', {})
    )
    units = shares_data.get('units', {})
    share_entries = units.get('shares', [])

    # Filter to 10-Q / 10-K filings via Pydantic; invalid entries are dropped
    _ta = TypeAdapter(list[SECCompanyFactShare])
    try:
        parsed = _ta.validate_python(share_entries)
    except ValidationError as exc:
        log.warning(f'[SEC] CompanyFacts schema mismatch for {ticker}: {exc}')
        return []

    filtered = [e for e in parsed if (e.form or '').startswith('10-')]
    filtered.sort(key=lambda x: x.end or '', reverse=True)

    return [
        {'end_date': e.end, 'shares': e.val, 'form': e.form}
        for e in filtered[:n_periods]
        if e.end and e.val is not None
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sleep(s: float = 0.12):
    """Respect SEC's 10 req/s guideline."""
    time.sleep(s)
