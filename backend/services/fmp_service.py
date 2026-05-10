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
from pydantic import TypeAdapter, ValidationError
from config import Config
from services.polygon_service import get_ticker_details
from validation.external_schemas import (
    FMPEarningsEvent,
    FMPProfile,
    FMPAnalystEstimate,
    FMPIncomeStatement,
    FMPKeyMetrics,
    FMPInsiderTransaction,
    FMPBalanceSheet,
    FMPInstitutionalHolder,
    FMPNewsItem,
)

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
    raw   = _get(f'historical/earning_calendar/{ticker.upper()}')

    if not raw or not isinstance(raw, list):
        return {'_source': 'fmp_unavailable', '_data_as_of': str(today)}

    _ta = TypeAdapter(list[FMPEarningsEvent])
    try:
        events = _ta.validate_python(raw)
    except ValidationError as exc:
        log.warning(f'[FMP] EarningsCalendar schema mismatch for {ticker}: {exc}')
        return {'_source': 'fmp_schema_error', '_data_as_of': str(today)}

    today_s   = str(today)
    upcoming  = [e for e in events if (e.date or '') >= today_s]
    past      = [e for e in events if (e.date or '') <  today_s]
    upcoming.sort(key=lambda x: x.date or '')
    past.sort(key=lambda x: x.date or '', reverse=True)

    next_event = upcoming[0] if upcoming else None

    return {
        'next_earnings_date':   next_event.date if next_event else None,
        'next_earnings_status': 'upcoming' if next_event else 'no upcoming date known',
        'eps_estimate':         next_event.epsEstimated if next_event else None,
        'revenue_estimate':     next_event.revenueEstimated if next_event else None,
        'history':              [e.model_dump() for e in past[:4]],
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
    raw = _get(f'profile/{ticker.upper()}')
    if not raw or not isinstance(raw, list) or not raw[0]:
        log.info(f'[FMP] Profile missing for {ticker}, trying Polygon fallback...')
        poly_data = get_ticker_details(ticker)
        if poly_data:
            poly_data['_data_as_of'] = str(_today_et().date())
            return poly_data
        return {}

    try:
        p = FMPProfile.model_validate(raw[0])
    except ValidationError as exc:
        log.warning(f'[FMP] Profile schema mismatch for {ticker}: {exc}')
        return {}

    today = _today_et().date()
    rng   = p.range or ''
    parts = rng.split('-')

    return {
        'ticker':             p.symbol,
        'company_name':       p.companyName,
        'sector':             p.sector,
        'industry':           p.industry,
        'description':        (p.description or '')[:500],
        'market_cap':         p.mktCap,
        'float_shares':       p.floatShares,
        'shares_outstanding': p.sharesOutstanding,
        'beta':               p.beta,
        'current_price':      p.price,
        'high_52w':           parts[-1] if len(parts) > 1 else None,
        'low_52w':            parts[0]  if parts else None,
        'avg_volume':         p.volAvg,
        'exchange':           p.exchangeShortName,
        'is_etf':             p.isEtf,
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
    raw = _get(f'analyst-estimates/{ticker.upper()}', {'period': 'quarter', 'limit': 4})
    if not raw or not isinstance(raw, list):
        return []

    _ta = TypeAdapter(list[FMPAnalystEstimate])
    try:
        estimates = _ta.validate_python(raw)
    except ValidationError as exc:
        log.warning(f'[FMP] AnalystEstimates schema mismatch for {ticker}: {exc}')
        return []

    return [
        {
            'date':                e.date,
            'eps_avg_estimate':    e.estimatedEpsAvg,
            'eps_high':            e.estimatedEpsHigh,
            'eps_low':             e.estimatedEpsLow,
            'revenue_avg':         e.estimatedRevenueAvg,
            'number_analysts_eps': e.numberAnalystEstimatedEps,
        }
        for e in estimates
    ]


# ---------------------------------------------------------------------------
# Public: Income Statement (trailing fundamentals)
# ---------------------------------------------------------------------------

def get_income_statement(ticker: str, quarters: int = 4) -> list[dict]:
    """
    Return trailing quarterly income statement data.
    Covers: revenue, gross profit, net income, EPS (basic/diluted).
    """
    raw = _get(f'income-statement/{ticker.upper()}',
               {'period': 'quarter', 'limit': quarters})
    if not raw or not isinstance(raw, list):
        return []

    _ta = TypeAdapter(list[FMPIncomeStatement])
    try:
        statements = _ta.validate_python(raw)
    except ValidationError as exc:
        log.warning(f'[FMP] IncomeStatement schema mismatch for {ticker}: {exc}')
        return []

    return [
        {
            'date':         e.date,
            'revenue':      e.revenue,
            'gross_profit': e.grossProfit,
            'net_income':   e.netIncome,
            'eps':          e.eps,
            'eps_diluted':  e.epsdiluted,
        }
        for e in statements
    ]


# ---------------------------------------------------------------------------
# Public: Key Metrics (short interest, P/E, P/S, debt, etc.)
# ---------------------------------------------------------------------------

def get_key_metrics(ticker: str) -> dict:
    """
    Return latest TTM key metrics: P/E, P/S, debt-to-equity, short interest,
    current ratio, free cash flow per share, etc.
    """
    raw = _get(f'key-metrics-ttm/{ticker.upper()}')
    if not raw or not isinstance(raw, list) or not raw[0]:
        return {}

    try:
        m = FMPKeyMetrics.model_validate(raw[0])
    except ValidationError as exc:
        log.warning(f'[FMP] KeyMetrics schema mismatch for {ticker}: {exc}')
        return {}

    return {
        'pe_ratio_ttm':          m.peRatioTTM,
        'ps_ratio_ttm':          m.priceToSalesRatioTTM,
        'pb_ratio_ttm':          m.pbRatioTTM,
        'debt_to_equity_ttm':    m.debtToEquityTTM,
        'current_ratio_ttm':     m.currentRatioTTM,
        'free_cashflow_ps_ttm':  m.freeCashFlowPerShareTTM,
        'revenue_ps_ttm':        m.revenuePerShareTTM,
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

    raw = _get('insider-trading',
               {'symbol': ticker.upper(), 'transactionType': 'P-Purchase,S-Sale', 'limit': 50})
    if not raw or not isinstance(raw, list):
        return {'net_shares': None, 'transactions': [], '_source': 'fmp_unavailable'}

    _ta = TypeAdapter(list[FMPInsiderTransaction])
    try:
        all_txns = _ta.validate_python(raw)
    except ValidationError as exc:
        log.warning(f'[FMP] InsiderTransactions schema mismatch for {ticker}: {exc}')
        return {'net_shares': None, 'transactions': [], '_source': 'fmp_schema_error'}

    recent = [t for t in all_txns if (t.transactionDate or '') >= cutoff]

    net = 0
    transactions = []
    for tx in recent:
        tx_type = tx.transactionType or ''
        shares  = int(tx.securitiesTransacted or 0)
        sign    = 1 if tx_type == 'P-Purchase' else -1
        net    += sign * shares
        transactions.append({
            'name':   tx.reportingName,
            'type':   tx_type,
            'shares': shares,
            'price':  tx.price,
            'date':   tx.transactionDate,
            'form':   tx.typeOfOwnership,
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
    raw = _get(f'balance-sheet-statement/{ticker.upper()}',
               {'period': 'quarter', 'limit': 1})
    if not raw or not isinstance(raw, list) or not raw[0]:
        return {}

    try:
        bs = FMPBalanceSheet.model_validate(raw[0])
    except ValidationError as exc:
        log.warning(f'[FMP] BalanceSheet schema mismatch for {ticker}: {exc}')
        return {}

    return {
        'cash':              bs.cashAndCashEquivalents,
        'total_assets':      bs.totalAssets,
        'total_liabilities': bs.totalLiabilities,
        'period':            bs.date,
        '_source':           'fmp',
    }


# ---------------------------------------------------------------------------
# Public: Institutional Holders
# ---------------------------------------------------------------------------

def get_institutional_holders(ticker: str) -> list[dict]:
    """
    Return top institutional holders from FMP.
    """
    raw = _get(f'institutional-holders/{ticker.upper()}')
    if not raw or not isinstance(raw, list):
        return []

    _ta = TypeAdapter(list[FMPInstitutionalHolder])
    try:
        holders = _ta.validate_python(raw)
    except ValidationError as exc:
        log.warning(f'[FMP] InstitutionalHolders schema mismatch for {ticker}: {exc}')
        return []

    return [
        {
            'holder': h.holder,
            'shares': h.shares,
            'date':   h.dateReported,
            'change': h.change,
        }
        for h in holders[:10]
    ]


# ---------------------------------------------------------------------------
# Public: Stock News (FMP variant)
# ---------------------------------------------------------------------------

def get_stock_news(ticker: str, limit: int = 10) -> list[dict]:
    """
    Return recent news articles for a ticker from FMP.
    Often more comprehensive for small-caps than yfinance.
    """
    raw = _get('stock_news', {'tickers': ticker.upper(), 'limit': limit})
    if not raw or not isinstance(raw, list):
        return []

    _ta = TypeAdapter(list[FMPNewsItem])
    try:
        articles = _ta.validate_python(raw)
    except ValidationError as exc:
        log.warning(f'[FMP] StockNews schema mismatch for {ticker}: {exc}')
        return []

    return [
        {
            'title': a.title,
            'text':  a.text,
            'url':   a.url,
            'date':  a.publishedDate,
            'site':  a.site,
        }
        for a in articles
    ]
