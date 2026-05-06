"""
pipe_service.py — Private Placement (PIPE) 8-K Scanner.

Detects whether a stock has a recent private placement filing near a gainer
event date. Classifies the deal as favorable or toxic based on structure.

Uses SEC EDGAR APIs (no key required) via the shared sec_service infrastructure.
"""
import re
import json
import logging
import requests
from datetime import datetime, timedelta
from services.sec_service import (
    get_cik_from_ticker, _SUBMISSIONS_URL, _HEADERS, _sleep, get_shares_history,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal dictionaries
# ---------------------------------------------------------------------------

PIPE_ITEM_CODES = {'1.01', '3.02'}

PIPE_POSITIVE_KEYWORDS = [
    'private placement', 'securities purchase agreement',
    'registered direct', 'pipe transaction', 'pipe financing',
    'aggregate gross proceeds', 'private offering', 'accredited investor',
    'institutional investor', 'strategic investor',
]

FIXED_PRICE_KEYWORDS = [
    'fixed price', 'purchase price of $', 'price of $',
    'per share price', 'at a price per share',
]

TOXIC_KEYWORDS = [
    'variable rate', 'floating conversion', 'variable conversion',
    'lowest vwap', 'lowest closing price', 'lowest traded price',
    'adjustable conversion', 'death spiral', 'floor price',
    'full ratchet', 'anti-dilution', 'most favored nation',
    'equity line of credit', 'standby equity distribution',
    'variable priced', 'market price conversion',
    'lowest bid', 'percentage of market',
]

SECURITY_TYPE_MAP = {
    'common_stock':     ['common stock', 'shares of common', 'common shares'],
    'preferred_stock':  ['preferred stock', 'series a preferred', 'series b preferred'],
    'convertible_note': ['convertible note', 'convertible debenture', 'convertible promissory'],
    'warrant':          ['warrant', 'purchase warrant'],
}

UOP_GROWTH_KEYWORDS = [
    'clinical trial', 'fda', 'acquisition', 'merger', 'expansion',
    'research and development', 'r&d', 'capital expenditure',
    'strategic partnership', 'product development', 'alliance',
]

UOP_GENERIC_KEYWORDS = [
    'working capital', 'general corporate purposes', 'operating expenses',
    'repay', 'refinanc', 'pay down', 'outstanding indebtedness',
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_pipe_filing(ticker: str, anchor_date: str | None = None,
                       days_back: int = 14, days_forward: int = 2) -> dict:
    """
    Scan 8-K filings for a ticker near anchor_date for PIPE signals.

    Args:
        ticker:       Stock ticker symbol.
        anchor_date:  The gainer event date (YYYY-MM-DD). Defaults to today.
        days_back:    Days before anchor_date to include filings.
        days_forward: Days after anchor_date to include filings.

    Returns:
        Structured dict with PIPE detection results.
    """
    from datetime import timezone
    if not anchor_date:
        anchor_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    result = _empty_result(ticker, anchor_date)

    cik = get_cik_from_ticker(ticker)
    if not cik:
        log.warning(f'[PIPE] No CIK for {ticker}')
        return result

    try:
        _sleep()
        resp = requests.get(_SUBMISSIONS_URL.format(cik=cik), headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f'[PIPE] Submissions fetch failed for {ticker}: {e}')
        return result

    recent       = data.get('filings', {}).get('recent', {})
    form_types   = recent.get('form', [])
    filed_dates  = recent.get('filingDate', [])
    accessions   = recent.get('accessionNumber', [])
    items_list   = recent.get('items', [])
    primary_docs = recent.get('primaryDocument', [])

    anchor_dt = datetime.strptime(anchor_date, '%Y-%m-%d')
    cutoff    = anchor_dt - timedelta(days=days_back)
    ceiling   = anchor_dt + timedelta(days=days_forward)

    best_filing = None
    for form, filed, acc, items_raw, pdoc in zip(
        form_types, filed_dates, accessions, items_list, primary_docs
    ):
        if not form.upper().startswith('8-K'):
            continue
        try:
            filed_dt = datetime.strptime(filed, '%Y-%m-%d')
        except ValueError:
            continue
        if filed_dt < cutoff or filed_dt > ceiling:
            continue

        raw_codes  = str(items_raw or '').replace(';', ',').split(',')
        item_codes = {c.strip() for c in raw_codes if c.strip()}

        if not item_codes.intersection(PIPE_ITEM_CODES):
            continue

        days_diff = abs((filed_dt - anchor_dt).days)
        if best_filing is None or days_diff < best_filing['days_diff']:
            acc_clean = acc.replace('-', '')
            url = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{pdoc}'
            best_filing = {
                'filed': filed, 'acc': acc, 'url': url,
                'item_codes': item_codes, 'days_diff': days_diff,
            }

    if not best_filing:
        return result

    result['filing_date']      = best_filing['filed']
    result['accession_number'] = best_filing['acc']
    result['filing_url']       = best_filing['url']
    result['item_codes']       = list(best_filing['item_codes'])

    body_text = _fetch_filing_text(best_filing['url'])
    if not body_text:
        if '3.02' in best_filing['item_codes']:
            result['is_pipe']    = True
            result['deal_score'] = 2
        return result

    body_lower    = body_text.lower()
    pipe_kw_hits  = [kw for kw in PIPE_POSITIVE_KEYWORDS if kw in body_lower]

    if not pipe_kw_hits and '3.02' not in best_filing['item_codes']:
        return result

    result['is_pipe']          = True
    result['raw_text_snippet'] = body_text[:600].strip()

    # Security type
    for stype, keywords in SECURITY_TYPE_MAP.items():
        if any(kw in body_lower for kw in keywords):
            result['security_type'] = stype
            break

    # Pricing type
    toxic_hits = [kw for kw in TOXIC_KEYWORDS if kw in body_lower]
    fixed_hits = [kw for kw in FIXED_PRICE_KEYWORDS if kw in body_lower]
    if toxic_hits:
        result['pricing_type']  = 'variable'
        result['toxic_signals'] = toxic_hits
    elif fixed_hits:
        result['pricing_type'] = 'fixed'
    else:
        result['pricing_type'] = 'unknown'

    result['proceeds_amount'] = _extract_proceeds(body_lower)

    # Use of proceeds
    growth_hits  = [kw for kw in UOP_GROWTH_KEYWORDS if kw in body_lower]
    generic_hits = [kw for kw in UOP_GENERIC_KEYWORDS if kw in body_lower]
    if growth_hits:
        result['use_of_proceeds'] = 'growth: ' + ', '.join(growth_hits[:3])
    elif generic_hits:
        result['use_of_proceeds'] = 'generic: ' + ', '.join(generic_hits[:3])
    else:
        result['use_of_proceeds'] = 'unspecified'

    result['deal_score'] = _score_deal(result)
    return result


def build_pipe_payload(ticker: str, anchor_date: str | None = None) -> dict:
    """Full payload for the PIPE LLM analysis prompt."""
    pipe         = detect_pipe_filing(ticker, anchor_date)
    shares_hist  = get_shares_history(ticker, n_periods=6)
    prior_pipes  = _count_prior_pipes(ticker, anchor_date)
    return {
        'ticker':           ticker,
        'anchor_date':      anchor_date,
        'pipe_filing':      pipe,
        'shares_history':   shares_hist,
        'prior_pipe_count': prior_pipes,
    }


def batch_scan_gainers(date: str) -> list[dict]:
    """
    Scan all gainers for a given date for PIPE signals.
    Checks the pipe_filings cache first; scans EDGAR only for misses.
    Returns a list of dicts (one per gainer, ordered by gap_pct DESC).
    """
    from database import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker FROM daily_gainers WHERE date = %s ORDER BY gap_pct DESC LIMIT 9",
            (date,),
        ).fetchall()

    if not rows:
        return []

    results = []
    for row in rows:
        ticker = row['ticker']
        cached = _get_cached_scan(ticker, date)
        if cached:
            results.append(cached)
            continue

        detection = detect_pipe_filing(ticker, anchor_date=date, days_back=14, days_forward=2)
        _upsert_scan(ticker, date, detection)
        results.append({'ticker': ticker, **detection})

    return results


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_cached_scan(ticker: str, anchor_date: str) -> dict | None:
    from database import get_connection
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pipe_filings WHERE ticker = %s AND anchor_date = %s LIMIT 1",
                (ticker, anchor_date),
            ).fetchone()
        if row:
            d = dict(row)
            d['toxic_signals'] = json.loads(d.get('toxic_signals') or '[]')
            return d
    except Exception as e:
        log.warning(f'[PIPE] Cache lookup failed: {e}')
    return None


def _upsert_scan(ticker: str, anchor_date: str, detection: dict):
    from database import get_connection
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO pipe_filings
                   (ticker, anchor_date, filing_date, accession_number, is_pipe,
                    security_type, pricing_type, proceeds_amount, use_of_proceeds,
                    investor_names, toxic_signals, deal_score, raw_items, filing_url)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (ticker, anchor_date) DO UPDATE SET
                     filing_date      = EXCLUDED.filing_date,
                     accession_number = EXCLUDED.accession_number,
                     is_pipe          = EXCLUDED.is_pipe,
                     security_type    = EXCLUDED.security_type,
                     pricing_type     = EXCLUDED.pricing_type,
                     proceeds_amount  = EXCLUDED.proceeds_amount,
                     use_of_proceeds  = EXCLUDED.use_of_proceeds,
                     toxic_signals    = EXCLUDED.toxic_signals,
                     deal_score       = EXCLUDED.deal_score,
                     raw_items        = EXCLUDED.raw_items,
                     filing_url       = EXCLUDED.filing_url,
                     scanned_at       = NOW()""",
                (
                    ticker, anchor_date,
                    detection.get('filing_date'),
                    detection.get('accession_number'),
                    detection.get('is_pipe', False),
                    detection.get('security_type'),
                    detection.get('pricing_type'),
                    detection.get('proceeds_amount'),
                    detection.get('use_of_proceeds'),
                    detection.get('investor_names'),
                    json.dumps(detection.get('toxic_signals', [])),
                    detection.get('deal_score'),
                    ','.join(detection.get('item_codes', [])),
                    detection.get('filing_url'),
                ),
            )
    except Exception as e:
        log.warning(f'[PIPE] Upsert failed for {ticker}/{anchor_date}: {e}')


def _count_prior_pipes(ticker: str, anchor_date: str | None) -> int:
    from database import get_connection
    try:
        with get_connection() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM pipe_filings
                   WHERE ticker = %s AND is_pipe = TRUE
                   AND (%s IS NULL OR anchor_date < %s)""",
                (ticker, anchor_date, anchor_date),
            ).fetchone()
        return int(row['cnt']) if row else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _fetch_filing_text(url: str) -> str | None:
    """Download 8-K HTML and strip to plain text (capped at 60KB)."""
    try:
        _sleep(0.2)
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        clean = re.sub(r'<[^>]+>', ' ', resp.text)
        clean = re.sub(r'\s+', ' ', clean)
        return clean[:60000]
    except Exception as e:
        log.warning(f'[PIPE] Filing fetch failed ({url[:60]}): {e}')
        return None


def _extract_proceeds(text_lower: str) -> float | None:
    patterns = [
        r'aggregate\s+(?:gross\s+)?proceeds\s+of\s+\$\s*([\d,]+(?:\.\d+)?)\s*million',
        r'gross\s+proceeds\s+of\s+(?:approximately\s+)?\$\s*([\d,]+(?:\.\d+)?)\s*million',
        r'\$\s*([\d,]+(?:\.\d+)?)\s*million\s+(?:in|of)\s+(?:gross\s+)?proceeds',
        r'aggregate\s+proceeds\s+of\s+\$\s*([\d,]+(?:\.\d+)?)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text_lower)
        if m:
            try:
                val = float(m.group(1).replace(',', ''))
                return val * 1_000_000 if 'million' in pattern else val
            except (ValueError, IndexError):
                continue
    return None


def _score_deal(result: dict) -> int:
    """Score the deal 1 (toxic) to 5 (favorable)."""
    score = 3

    if result.get('pricing_type') == 'fixed':
        score += 1
    elif result.get('pricing_type') == 'variable':
        score -= 1

    n_toxic = len(result.get('toxic_signals', []))
    if n_toxic == 0:
        score += 1
    elif n_toxic >= 3:
        score -= 2
    elif n_toxic >= 1:
        score -= 1

    stype = result.get('security_type', '')
    if stype == 'convertible_note':
        score -= 1
    elif stype == 'common_stock':
        score += 1

    uop = result.get('use_of_proceeds', '')
    if uop and uop.startswith('growth'):
        score += 1
    elif uop and uop.startswith('generic'):
        score -= 1

    return max(1, min(5, score))


def _empty_result(ticker: str, anchor_date: str) -> dict:
    return {
        'ticker':           ticker,
        'anchor_date':      anchor_date,
        'is_pipe':          False,
        'filing_date':      None,
        'accession_number': None,
        'filing_url':       None,
        'security_type':    None,
        'pricing_type':     None,
        'proceeds_amount':  None,
        'use_of_proceeds':  None,
        'investor_names':   None,
        'toxic_signals':    [],
        'deal_score':       None,
        'item_codes':       [],
        'raw_text_snippet': None,
    }
