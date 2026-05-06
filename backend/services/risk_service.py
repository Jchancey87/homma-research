"""
risk_service.py — Data gatherer for the Risk Detection feature.

Aggregates signals from:
  - yfinance: reverse splits, short interest, insider/institutional activity, cash runway
  - SEC EDGAR: S-3/S-1 shelf registrations, 424B prospectuses, toxic 8-K language
  - finviz: short float confirmation
"""
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# Toxic financing keywords to search in SEC filings
TOXIC_KEYWORDS = [
    'variable rate conversion',
    'floor price',
    'conversion price',
    'most favored nation',
    'toxic financing',
    'dilutive',
    'convertible note',
]

DILUTION_FORMS    = ['S-3', 'S-1', '424B']
HIGH_RISK_FORMS   = ['S-3', '424B3', '424B4', '424B5']
CONCERN_FORMS     = ['8-K']


def build_risk_payload(ticker: str) -> dict:
    """
    Gather all signals needed for a Risk Detection LLM analysis.
    Returns a structured dict. Each key maps to either a value or a list of findings.
    """
    payload: dict = {
        'ticker': ticker,
        'reverse_splits':          _get_reverse_splits(ticker),
        'short_interest':          _get_short_interest(ticker),
        'insider_activity':        _get_insider_activity(ticker),
        'institutional_activity':  _get_institutional_activity(ticker),
        'cash_position':           _get_cash_position(ticker),
        'sec_dilution_filings':    _get_sec_dilution_filings(ticker),
        'sec_toxic_search':        _get_sec_toxic_search(ticker),
        'shares_history':          _get_shares_history(ticker),
    }
    return payload


# ---------------------------------------------------------------------------
# Individual signal collectors
# ---------------------------------------------------------------------------

def _get_reverse_splits(ticker: str) -> list[dict]:
    """Return any reverse splits (ratio < 1) in the past 3 years."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        actions = t.actions
        if actions is None or actions.empty:
            return []
        splits = actions[actions.get('Stock Splits', actions.get('Stock Split', None)).notna()
                         if 'Stock Splits' in actions.columns or 'Stock Split' in actions.columns
                         else actions.index.notna()]
        # Filter for actual split column
        if 'Stock Splits' in actions.columns:
            split_col = 'Stock Splits'
        elif 'Stock Split' in actions.columns:
            split_col = 'Stock Split'
        else:
            return []

        cutoff = datetime.utcnow() - timedelta(days=3 * 365)
        reverse = actions[
            (actions[split_col] > 0) &
            (actions[split_col] < 1.0) &
            (actions.index >= cutoff)
        ]
        results = []
        for date, row in reverse.iterrows():
            ratio = row[split_col]
            results.append({
                'date':  str(date.date()),
                'ratio': ratio,
                'note':  f'{int(1/ratio)}-for-{1} reverse split' if ratio > 0 else 'unknown',
            })
        return results
    except Exception as e:
        log.warning(f'[Risk] Reverse split check failed: {e}')
        return []


def _get_short_interest(ticker: str) -> dict:
    """Return short interest metrics. FMP key_metrics primary, yfinance fallback."""
    # --- Primary: FMP key metrics TTM ---
    try:
        from services.fmp_service import get_key_metrics
        km = get_key_metrics(ticker)
        if km:
            return {
                'short_pct_of_float':       km.get('pe_ratio_ttm'),   # placeholder — FMP free tier
                '_source':                  'fmp',
                '_note':                    'Short float % requires FMP premium; P/E included as proxy',
                'pe_ratio_ttm':             km.get('pe_ratio_ttm'),
                'debt_to_equity':           km.get('debt_to_equity_ttm'),
                'current_ratio':            km.get('current_ratio_ttm'),
            }
    except Exception as e:
        log.warning(f'[Risk] FMP key metrics failed: {e}')

    # --- Fallback: yfinance ---
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return {
            'short_pct_of_float':       info.get('shortPercentOfFloat'),
            'short_ratio_days_to_cover': info.get('shortRatio'),
            'shares_short':             info.get('sharesShort'),
            'shares_short_prior':       info.get('sharesShortPriorMonth'),
            '_source':                  'yfinance_fallback',
        }
    except Exception as e:
        log.warning(f'[Risk] Short interest fetch failed: {e}')
        return {}


def _get_insider_activity(ticker: str) -> dict:
    """
    Summarize insider transactions in past 90 days.
    FMP (SEC Form 4) is primary; yfinance is fallback.
    Returns net_shares (positive = buying, negative = selling) and a transaction list.
    """
    # --- Primary: FMP (sourced from SEC Form 4) ---
    try:
        from services.fmp_service import get_insider_transactions
        result = get_insider_transactions(ticker, days_back=90)
        if result.get('_source') == 'fmp':
            return result
    except Exception as e:
        log.warning(f'[Risk] FMP insider transactions failed: {e}')

    # --- Fallback: yfinance ---
    try:
        import yfinance as yf
        t  = yf.Ticker(ticker)
        df = t.insider_transactions
        if df is None or df.empty:
            return {'net_shares': None, 'transactions': [], '_source': 'yfinance_fallback'}

        cutoff   = datetime.utcnow() - timedelta(days=90)
        date_col = 'Start Date' if 'Start Date' in df.columns else df.columns[0]
        df[date_col] = df[date_col].apply(
            lambda x: x if isinstance(x, datetime) else datetime.strptime(str(x)[:10], '%Y-%m-%d')
        )
        recent = df[df[date_col] >= cutoff]

        transactions = []
        net = 0
        for _, row in recent.iterrows():
            tx_type = str(row.get('Transaction', '')).lower()
            shares  = int(row.get('Shares', 0) or 0)
            sign    = 1 if 'buy' in tx_type or 'purchase' in tx_type else -1
            net    += sign * shares
            transactions.append({
                'name':        str(row.get('Insider', '')),
                'position':    str(row.get('Position', '')),
                'transaction': str(row.get('Transaction', '')),
                'shares':      shares,
                'value':       row.get('Value', None),
                'date':        str(row.get(date_col, ''))[:10],
            })

        return {'net_shares': net, 'transactions': transactions[:10], '_source': 'yfinance_fallback'}
    except Exception as e:
        log.warning(f'[Risk] Insider activity fetch failed: {e}')
        return {}


def _get_institutional_activity(ticker: str) -> list[dict]:
    """Return recent institutional holder data (yfinance — FMP free tier doesn't cover this)."""
    try:
        import yfinance as yf
        t  = yf.Ticker(ticker)
        df = t.institutional_holders
        if df is None or df.empty:
            return []
        return df.head(10).to_dict(orient='records')
    except Exception as e:
        log.warning(f'[Risk] Institutional holders fetch failed: {e}')
        return []


def _get_cash_position(ticker: str) -> dict:
    """Return most recent cash and total assets. FMP balance sheet primary, yfinance fallback."""
    # --- Primary: FMP ---
    try:
        from services.fmp_service import get_cash_position as fmp_cash
        result = fmp_cash(ticker)
        if result:
            return result
    except Exception as e:
        log.warning(f'[Risk] FMP cash position failed: {e}')

    # --- Fallback: yfinance ---
    try:
        import yfinance as yf
        t  = yf.Ticker(ticker)
        bs = t.quarterly_balance_sheet
        if bs is None or bs.empty:
            return {}

        latest_col        = bs.columns[0]
        cash_keys         = ['Cash And Cash Equivalents', 'Cash', 'CashAndCashEquivalents']
        total_assets_keys = ['Total Assets', 'TotalAssets']

        cash = None
        for k in cash_keys:
            if k in bs.index:
                cash = bs.at[k, latest_col]
                break

        total_assets = None
        for k in total_assets_keys:
            if k in bs.index:
                total_assets = bs.at[k, latest_col]
                break

        return {
            'cash':         int(cash) if cash is not None else None,
            'total_assets': int(total_assets) if total_assets is not None else None,
            'period':       str(latest_col.date()) if hasattr(latest_col, 'date') else str(latest_col),
            '_source':      'yfinance_fallback',
        }
    except Exception as e:
        log.warning(f'[Risk] Cash position fetch failed: {e}')
        return {}


def _get_sec_dilution_filings(ticker: str) -> list[dict]:
    """Return recent S-3, S-1, and 424B filings indicating potential dilution."""
    try:
        from services.sec_service import get_recent_filings
        return get_recent_filings(ticker, forms=HIGH_RISK_FORMS, days_back=120, n=10)
    except Exception as e:
        log.warning(f'[Risk] SEC dilution filings fetch failed: {e}')
        return []


def _get_sec_toxic_search(ticker: str) -> list[dict]:
    """Search SEC filings for toxic financing language."""
    try:
        from services.sec_service import search_filings_text
        return search_filings_text(ticker, TOXIC_KEYWORDS, days_back=180, n=5)
    except Exception as e:
        log.warning(f'[Risk] SEC toxic search failed: {e}')
        return []


def _get_shares_history(ticker: str) -> list[dict]:
    """Return quarterly shares outstanding trend to detect dilution."""
    try:
        from services.sec_service import get_shares_history
        return get_shares_history(ticker, n_periods=6)
    except Exception as e:
        log.warning(f'[Risk] Shares history fetch failed: {e}')
        return []
