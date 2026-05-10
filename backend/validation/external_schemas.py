"""
validation/external_schemas.py
-------------------------------
Pydantic v2 schemas for validating raw JSON responses from external APIs.

Sources covered:
  - Financial Modeling Prep (FMP)
  - SEC EDGAR (Submissions, EFTS, XBRL Company Facts)

Design: All models use `model_config = ConfigDict(extra='ignore')` so any
*new* fields added by the upstream API are silently ignored without error.
Fields that are legitimately optional in the real API are typed as
`Optional[X] = None` — Pydantic will coerce missing keys to None rather than
raising a validation error, which is the behaviour we want for a data pipeline
that must stay up even when providers return incomplete records.

Usage pattern (inside a service):
    from pydantic import TypeAdapter, ValidationError
    from validation.external_schemas import FMPProfile

    raw = _get(f'profile/{ticker}')   # returns list or None
    if not raw:
        return {}
    try:
        profile = FMPProfile.model_validate(raw[0])
    except ValidationError as exc:
        log.warning(f'[FMP] Profile schema mismatch for {ticker}: {exc}')
        return {}
    return profile.model_dump()
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Shared base config
# ─────────────────────────────────────────────────────────────────────────────

class _BaseExternal(BaseModel):
    """Base for all external API schemas: ignore unknown fields."""
    model_config = ConfigDict(extra='ignore', populate_by_name=True)


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Earnings Calendar
# ─────────────────────────────────────────────────────────────────────────────

class FMPEarningsEvent(_BaseExternal):
    """One row from /historical/earning_calendar/{ticker}."""
    date: Optional[str] = None
    symbol: Optional[str] = None
    epsEstimated: Optional[float] = None           # noqa: N815
    revenueEstimated: Optional[float] = None       # noqa: N815
    eps: Optional[float] = None
    revenue: Optional[float] = None
    updatedFromDate: Optional[str] = None          # noqa: N815
    fiscalDateEnding: Optional[str] = None         # noqa: N815


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Company Profile
# ─────────────────────────────────────────────────────────────────────────────

class FMPProfile(_BaseExternal):
    """One element from /profile/{ticker} list response."""
    symbol: Optional[str] = None
    companyName: Optional[str] = None             # noqa: N815
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    mktCap: Optional[float] = None                # noqa: N815
    floatShares: Optional[float] = None           # noqa: N815
    sharesOutstanding: Optional[float] = None     # noqa: N815
    beta: Optional[float] = None
    price: Optional[float] = None
    range: Optional[str] = None
    volAvg: Optional[int] = None                  # noqa: N815
    exchangeShortName: Optional[str] = None       # noqa: N815
    isEtf: Optional[bool] = False                 # noqa: N815


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Analyst Estimates
# ─────────────────────────────────────────────────────────────────────────────

class FMPAnalystEstimate(_BaseExternal):
    """One row from /analyst-estimates/{ticker}."""
    date: Optional[str] = None
    estimatedEpsAvg: Optional[float] = None       # noqa: N815
    estimatedEpsHigh: Optional[float] = None      # noqa: N815
    estimatedEpsLow: Optional[float] = None       # noqa: N815
    estimatedRevenueAvg: Optional[float] = None   # noqa: N815
    numberAnalystEstimatedEps: Optional[int] = None   # noqa: N815


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Income Statement
# ─────────────────────────────────────────────────────────────────────────────

class FMPIncomeStatement(_BaseExternal):
    """One row from /income-statement/{ticker}."""
    date: Optional[str] = None
    revenue: Optional[float] = None
    grossProfit: Optional[float] = None           # noqa: N815
    netIncome: Optional[float] = None             # noqa: N815
    eps: Optional[float] = None
    epsdiluted: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Key Metrics (TTM)
# ─────────────────────────────────────────────────────────────────────────────

class FMPKeyMetrics(_BaseExternal):
    """One element from /key-metrics-ttm/{ticker} list response."""
    peRatioTTM: Optional[float] = None            # noqa: N815
    priceToSalesRatioTTM: Optional[float] = None  # noqa: N815
    pbRatioTTM: Optional[float] = None            # noqa: N815
    debtToEquityTTM: Optional[float] = None       # noqa: N815
    currentRatioTTM: Optional[float] = None       # noqa: N815
    freeCashFlowPerShareTTM: Optional[float] = None   # noqa: N815
    revenuePerShareTTM: Optional[float] = None    # noqa: N815


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Insider Transactions
# ─────────────────────────────────────────────────────────────────────────────

class FMPInsiderTransaction(_BaseExternal):
    """One row from /insider-trading."""
    transactionDate: Optional[str] = None         # noqa: N815
    transactionType: Optional[str] = None         # noqa: N815
    reportingName: Optional[str] = None           # noqa: N815
    securitiesTransacted: Optional[float] = None  # noqa: N815
    price: Optional[float] = None
    typeOfOwnership: Optional[str] = None         # noqa: N815

    @field_validator('securitiesTransacted', mode='before')
    @classmethod
    def coerce_shares(cls, v):
        """FMP occasionally returns shares as a string."""
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Balance Sheet
# ─────────────────────────────────────────────────────────────────────────────

class FMPBalanceSheet(_BaseExternal):
    """One element from /balance-sheet-statement/{ticker} list response."""
    date: Optional[str] = None
    cashAndCashEquivalents: Optional[float] = None    # noqa: N815
    totalAssets: Optional[float] = None               # noqa: N815
    totalLiabilities: Optional[float] = None          # noqa: N815


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Institutional Holders
# ─────────────────────────────────────────────────────────────────────────────

class FMPInstitutionalHolder(_BaseExternal):
    """One row from /institutional-holders/{ticker}."""
    holder: Optional[str] = None
    shares: Optional[float] = None
    dateReported: Optional[str] = None            # noqa: N815
    change: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# FMP — Stock News
# ─────────────────────────────────────────────────────────────────────────────

class FMPNewsItem(_BaseExternal):
    """One row from /stock_news."""
    title: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None
    publishedDate: Optional[str] = None           # noqa: N815
    site: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# SEC — Submissions API (filing list item)
# ─────────────────────────────────────────────────────────────────────────────

class SECFilingItem(_BaseExternal):
    """
    Represents one zipped row across the parallel arrays inside
    filings.recent: { form, filingDate, primaryDocument, accessionNumber }.
    """
    form: Optional[str] = None
    filed: Optional[str] = None           # renamed from filingDate at parse time
    description: Optional[str] = None    # renamed from primaryDocument
    accession_number: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# SEC — EFTS Full-Text Search hit
# ─────────────────────────────────────────────────────────────────────────────

class SECEFTSSource(_BaseExternal):
    """The _source block inside an EFTS search hit."""
    entity_name: Optional[str] = None
    file_date: Optional[str] = None
    form_type: Optional[str] = None
    display_names: Optional[list[str]] = None


class SECEFTSHit(_BaseExternal):
    """One hit element from the EFTS search response."""
    _source: Optional[SECEFTSSource] = None      # noqa: N815

    # Pydantic does not auto-map leading-underscore fields from dict;
    # we handle this manually in sec_service via .get('_source', {}).
    # This schema is mainly used for the inner SECEFTSSource.


# ─────────────────────────────────────────────────────────────────────────────
# SEC — XBRL Company Facts (shares outstanding entry)
# ─────────────────────────────────────────────────────────────────────────────

class SECCompanyFactShare(_BaseExternal):
    """
    One element from:
    facts.us-gaap.CommonStockSharesOutstanding.units.shares[]
    """
    end: Optional[str] = None
    val: Optional[float] = None
    form: Optional[str] = None
    accn: Optional[str] = None
    fy: Optional[int] = None
    fp: Optional[str] = None
    frame: Optional[str] = None

    @field_validator('val', mode='before')
    @classmethod
    def coerce_val(cls, v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
