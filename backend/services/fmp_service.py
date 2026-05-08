"""
fmp_service.py — Financial Modeling Prep (FMP) API client.

Used as the PRIMARY source for:
  - Earnings calendar (confirmed upcoming dates + EPS estimates)
  - Company profile (float, shares outstanding, sector, beta, market cap)
  - Analyst EPS/revenue estimates
  - Income statement (trailing EPS, revenue)
  - Key metrics (short interest, P/E, etc.)

yfinance is kept as a fallback when FMP returns no data or the API key
is not configured.

Free tier: 250 requests/day — https://financialmodelingprep.com/developer/docs
"""
import logging
import requests
import pytz
from datetime import datetime, timedelta
from config import Config

log = logging.getLogger(__name__)

_BASE = 'https://financialmodelingprep.com/api'
_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None, version: int = 3) -> dict | list | None:
    """
    Make a GET request to the FMP API.
    Returns parsed JSON or None on error / missing key.
    """
    api_key = Config.FMP_API_KEY
    if not api_key:
        log.debug('[FMP] FMP_API_KEY not configured — skipping FMP call.')
        return None

    url = f'{_BASE}/v{version}/{path}'
    p   = {'apikey': api_key}
    if params:
        p.update(params)

    try:
        resp = requests.get(url, params=p, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # FMP returns {"Error Message": "..."} on bad key / unknown ticker
        if isinstance(data, dict) and 'Error Message' in data:
            log.warning(f'[FMP] API error for {path}: {data["Error Message"]}')
            return None
        return data
    except Exception as e:
        log.warning(f'[FMP] Request failed for {path}: {e}')
        return None


def _today_et() -> datetime:
    return datetime.now(pytz.timezone('America/New_York'))


# ---------------------------------------------------------------------------
# Public: Earnings Calendar
# ---------------------------------------------------------------------------

def get_earnings_calendar(ticker: str) -> dict:
    """
    Return the next confirmed earnings date (and prior actuals) for a ticker.

    Response shape:
        {
          'next_earnings_date':   'YYYY-MM-DD' or None,
          'next_earnings_status': 'upcoming' | 'PAST — already occurred' | 'unknown',
          'eps_estimate':         float or None,
          'revenue_estimate':     float or None,
          'history': [
              {'date': 'YYYY-MM-DD', 'eps': float, 'epsEstimated': float,
               'revenue': float, 'revenueEstimated': float}, ...
          ],
          '_source':     'fmp',
          '_data_as_of': 'YYYY-MM-DD',
        }
    """
    today = _today_et().date()
    data  = _get(f'historical/earning_calendar/{ticker.upper()}')

    if not data or not isinstance(data, list):
        return {'_source': 'fmp_unavailable', '_data_as_of': str(today)}

    # Split into upcoming (date >= today) and past
    upcoming = [e for e in data if e.get('date', '') >= str(today)]
    past     = [e for e in data if e.get('date', '') <  str(today)]

    # Sort: soonest upcoming first, most recent past first
    upcoming.sort(key=lambda x: x.get('date', ''))
    past.sort(key=lambda x: x.get('date', ''), reverse=True)

    next_event = upcoming[0] if upcoming else None

    return {
        'next_earnings_date':   next_event['date'] if next_event else None,
        'next_earnings_status': 'upcoming' if next_event else 'no upcoming date known',
        'eps_estimate':         next_event.get('epsEstimated') if next_event else None,
        'revenue_estimate':     next_event.get('revenueEstimated') if next_event else None,
        'history':              past[:4],   # last 4 reported quarters
        '_source':              'fmp',
        '_data_as_of':          str(today),
    }


# ---------------------------------------------------------------------------
# Public: Company Profile (replaces yfinance .info for key fields)
# ---------------------------------------------------------------------------

def get_company_profile(ticker: str) -> dict:
    """
    Return key company fundamentals from FMP's /profile endpoint.

    Covers: market cap, float, shares outstanding, beta, sector, industry,
    52-week high/low, average volume, current price, description.
    """
    data = _get(f'profile/{ticker.upper()}')
    if not data or not isinstance(data, list) or not data[0]:
        return {}

    p = data[0]
    today = _today_et().date()

    return {
        'ticker':             p.get('symbol'),
        'company_name':       p.get('companyName'),
        'sector':             p.get('sector'),
        'industry':           p.get('industry'),
        'description':        (p.get('description') or '')[:500],
        'market_cap':         p.get('mktCap'),
        'float_shares':       p.get('floatShares'),
        'shares_outstanding': p.get('sharesOutstanding'),
        'beta':               p.get('beta'),
        'current_price':      p.get('price'),
        'high_52w':           p.get('range', '').split('-')[-1] if p.get('range') else None,
        'low_52w':            p.get('range', '').split('-')[0]  if p.get('range') else None,
        'avg_volume':         p.get('volAvg'),
        'exchange':           p.get('exchangeShortName'),
        'is_etf':             p.get('isEtf', False),
        '_source':            'fmp',
        '_data_as_of':        str(today),
    }


# ---------------------------------------------------------------------------
# Public: Analyst Estimates (EPS / Revenue forecasts)
# ---------------------------------------------------------------------------

def get_analyst_estimates(ticker: str) -> list[dict]:
    """
    Return forward EPS and revenue estimates from analyst consensus.
    Returns a list of quarterly estimate records, most recent first.
    """
    data = _get(f'analyst-estimates/{ticker.upper()}', {'period': 'quarter', 'limit': 4})
    if not data or not isinstance(data, list):
        return []
    return [
        {
            'date':                e.get('date'),
            'eps_avg_estimate':    e.get('estimatedEpsAvg'),
            'eps_high':            e.get('estimatedEpsHigh'),
            'eps_low':             e.get('estimatedEpsLow'),
            'revenue_avg':         e.get('estimatedRevenueAvg'),
            'number_analysts_eps': e.get('numberAnalystEstimatedEps'),
        }
        for e in data
    ]


# ---------------------------------------------------------------------------
# Public: Income Statement (trailing fundamentals)
# ---------------------------------------------------------------------------

def get_income_statement(ticker: str, quarters: int = 4) -> list[dict]:
    """
    Return trailing quarterly income statement data.
    Covers: revenue, gross profit, net income, EPS (basic/diluted).
    """
    data = _get(f'income-statement/{ticker.upper()}',
                {'period': 'quarter', 'limit': quarters})
    if not data or not isinstance(data, list):
        return []
    return [
        {
            'date':         e.get('date'),
            'revenue':      e.get('revenue'),
            'gross_profit': e.get('grossProfit'),
            'net_income':   e.get('netIncome'),
            'eps':          e.get('eps'),
            'eps_diluted':  e.get('epsdiluted'),
        }
        for e in data
    ]


# ---------------------------------------------------------------------------
# Public: Key Metrics (short interest, P/E, P/S, debt, etc.)
# ---------------------------------------------------------------------------

def get_key_metrics(ticker: str) -> dict:
    """
    Return latest TTM key metrics: P/E, P/S, debt-to-equity, short interest,
    current ratio, free cash flow per share, etc.
    """
    data = _get(f'key-metrics-ttm/{ticker.upper()}')
    if not data or not isinstance(data, list) or not data[0]:
        return {}

    m = data[0]
    return {
        'pe_ratio_ttm':          m.get('peRatioTTM'),
        'ps_ratio_ttm':          m.get('priceToSalesRatioTTM'),
        'pb_ratio_ttm':          m.get('pbRatioTTM'),
        'debt_to_equity_ttm':    m.get('debtToEquityTTM'),
        'current_ratio_ttm':     m.get('currentRatioTTM'),
        'free_cashflow_ps_ttm':  m.get('freeCashFlowPerShareTTM'),
        'revenue_ps_ttm':        m.get('revenuePerShareTTM'),
        '_source':               'fmp',
    }


# ---------------------------------------------------------------------------
# Public: Insider Transactions
# ---------------------------------------------------------------------------

def get_insider_transactions(ticker: str, days_back: int = 90) -> dict:
    """
    Return recent insider buy/sell activity from FMP.
    More reliable than yfinance for small-caps (sourced from SEC Form 4).
    """
    today   = _today_et().date()
    cutoff  = (today - timedelta(days=days_back)).isoformat()

    data = _get(f'insider-trading',
                {'symbol': ticker.upper(), 'transactionType': 'P-Purchase,S-Sale', 'limit': 50})
    if not data or not isinstance(data, list):
        return {'net_shares': None, 'transactions': [], '_source': 'fmp_unavailable'}

    recent = [t for t in data if (t.get('transactionDate') or '') >= cutoff]

    net = 0
    transactions = []
    for tx in recent:
        tx_type = tx.get('transactionType', '')
        shares  = int(tx.get('securitiesTransacted') or 0)
        sign    = 1 if tx_type == 'P-Purchase' else -1
        net    += sign * shares
        transactions.append({
            'name':        tx.get('reportingName'),
            'type':        tx_type,
            'shares':      shares,
            'price':       tx.get('price'),
            'date':        tx.get('transactionDate'),
            'form':        tx.get('typeOfOwnership'),
        })

    return {
        'net_shares':   net,
        'transactions': transactions[:10],
        '_source':      'fmp',
        '_data_as_of':  str(today),
    }


# ---------------------------------------------------------------------------
# Public: Balance Sheet (cash position)
# ---------------------------------------------------------------------------

def get_cash_position(ticker: str) -> dict:
    """
    Return the most recent quarterly cash and total assets from FMP.
    More reliable for small-caps than yfinance's balance sheet scraper.
    """
    data = _get(f'balance-sheet-statement/{ticker.upper()}',
                {'period': 'quarter', 'limit': 1})
    if not data or not isinstance(data, list) or not data[0]:
        return {}

    bs = data[0]
    return {
        'cash':              bs.get('cashAndCashEquivalents'),
        'total_assets':      bs.get('totalAssets'),
        'total_liabilities': bs.get('totalLiabilities'),
        'period':            bs.get('date'),
        '_source':           'fmp',
    }


# ---------------------------------------------------------------------------
# Public: Institutional Holders
# ---------------------------------------------------------------------------

def get_institutional_holders(ticker: str) -> list[dict]:
    """
    Return top institutional holders from FMP.
    """
    data = _get(f'institutional-holders/{ticker.upper()}')
    if not data or not isinstance(data, list):
        return []
    return [
        {
            'holder':     e.get('holder'),
            'shares':     e.get('shares'),
            'date':       e.get('dateReported'),
            'change':     e.get('change'),
        }
        for e in data[:10]
    ]


# ---------------------------------------------------------------------------
# Public: Stock News (FMP variant)
# ---------------------------------------------------------------------------

def get_stock_news(ticker: str, limit: int = 10) -> list[dict]:
    """
    Return recent news articles for a ticker from FMP.
    Often more comprehensive for small-caps than yfinance.
    """
    data = _get('stock_news', {'tickers': ticker.upper(), 'limit': limit})
    if not data or not isinstance(data, list):
        return []
    return [
        {
            'title':     e.get('title'),
            'text':      e.get('text'),
            'url':       e.get('url'),
            'date':      e.get('publishedDate'),
            'site':      e.get('site'),
        }
        for e in data
    ]
