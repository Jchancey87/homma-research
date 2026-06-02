"""
validation/schemas.py
---------------------
Pydantic v2 request schemas for every API route group.

Conventions
-----------
- `ticker` fields are always uppercased and stripped via field_validator.
- `date` fields use `datetime.date` so Pydantic handles "YYYY-MM-DD" coercion.
  Routes that previously accepted an empty date as "optional" use `date | None`.
- `force` accepts bool *or* the string "true"/"1" from query strings.
- `limit` is always capped at 500 to prevent runaway queries.
- `tags` items are stripped of whitespace; empty strings are dropped.
- `sentiment` is a Literal so any value outside the set is rejected.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Literal, Optional

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _upper_strip(v: str) -> str:
    return v.upper().strip()


def _clean_tags(tags: list) -> list[str]:
    return [str(t).strip() for t in tags if str(t).strip()]


def _coerce_bool(v) -> bool:
    """Allow 'true', '1', 'yes' strings as True (needed for query params)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return bool(v)


# ---------------------------------------------------------------------------
# analysis.py — LLM job bodies
# ---------------------------------------------------------------------------

class ContinuationJobBody(BaseModel):
    """POST /continuation"""
    date: datetime.date

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")


class SentimentJobBody(BaseModel):
    """POST /sentiment"""
    query: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, v):
        return str(v).strip() if v else v


class TickerDateBody(BaseModel):
    """POST /research, /research/catalyst, /research/pipe"""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    date: Optional[datetime.date] = None
    force: bool = False

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    @field_validator("force", mode="before")
    @classmethod
    def coerce_force(cls, v):
        return _coerce_bool(v)


class TickerOnlyBody(BaseModel):
    """POST /research/risk, /research/context"""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    force: bool = False

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("force", mode="before")
    @classmethod
    def coerce_force(cls, v):
        return _coerce_bool(v)


# ---------------------------------------------------------------------------
# analysis.py — GET query schemas
# ---------------------------------------------------------------------------

class ChartDataQuery(BaseModel):
    """GET /research/chart-data"""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    date: datetime.date

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")


class ResearchHistoryQuery(BaseModel):
    """GET /research/history"""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    type: Optional[str] = None
    limit: Annotated[int, Field(ge=1, le=500)] = 50

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("limit", mode="before")
    @classmethod
    def coerce_limit(cls, v):
        return int(v) if v is not None else 50


class ListJobsQuery(BaseModel):
    """GET /jobs"""
    type: Optional[str] = None
    limit: Annotated[int, Field(ge=1, le=500)] = 50

    @field_validator("limit", mode="before")
    @classmethod
    def coerce_limit(cls, v):
        return int(v) if v is not None else 50


# ---------------------------------------------------------------------------
# observations.py
# ---------------------------------------------------------------------------

SentimentLiteral = Literal["bullish", "bearish", "neutral"]


class ObservationCreateBody(BaseModel):
    """POST /observations"""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    date: datetime.date
    body: Annotated[str, Field(min_length=1)]
    title: Optional[str] = None
    sentiment: SentimentLiteral = "neutral"
    tags: list[str] = []
    linked_chart_id: Optional[int] = None

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    @field_validator("body", mode="before")
    @classmethod
    def strip_body(cls, v):
        return str(v).strip() if v else v

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v):
        if not v:
            return None
        stripped = str(v).strip()
        return stripped or None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if not isinstance(v, list):
            raise ValueError("tags must be a JSON array")
        return _clean_tags(v)


class ObservationUpdateBody(BaseModel):
    """PUT /observations/<id> — all fields optional"""
    title: Optional[str] = None
    body: Optional[str] = None
    sentiment: Optional[SentimentLiteral] = None
    tags: Optional[list[str]] = None
    date: Optional[datetime.date] = None
    linked_chart_id: Optional[int] = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    @field_validator("body", mode="before")
    @classmethod
    def body_not_empty(cls, v):
        if v is not None and not str(v).strip():
            raise ValueError("body cannot be empty")
        return str(v).strip() if v else v

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        return _clean_tags(v)

    @model_validator(mode="after")
    def at_least_one_field(self):
        allowed = {"title", "body", "sentiment", "tags", "date", "linked_chart_id"}
        provided = {k for k in allowed if getattr(self, k) is not None}
        if not provided:
            raise ValueError("At least one field must be provided to update")
        return self


class ObservationFilterQuery(BaseModel):
    """GET /observations"""
    ticker: Optional[str] = None
    sentiment: Optional[SentimentLiteral] = None
    tag: Optional[str] = None
    date_from: Optional[datetime.date] = None
    date_to: Optional[datetime.date] = None
    limit: Annotated[int, Field(ge=1, le=500)] = 100

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        if not v:
            return None
        return _upper_strip(str(v))

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def parse_date(cls, v):
        if not v:
            return None
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    @field_validator("limit", mode="before")
    @classmethod
    def coerce_limit(cls, v):
        return int(v) if v is not None else 100


# ---------------------------------------------------------------------------
# watchlist.py
# ---------------------------------------------------------------------------

class WatchlistAddBody(BaseModel):
    """POST /watchlist"""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    sector: Optional[str] = None
    notes: Optional[str] = None
    tags: list[str] = []

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("sector", "notes", mode="before")
    @classmethod
    def strip_optional_str(cls, v):
        if not v:
            return None
        stripped = str(v).strip()
        return stripped or None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if not isinstance(v, list):
            raise ValueError("tags must be a JSON array")
        return _clean_tags(v)


class WatchlistUpdateBody(BaseModel):
    """PUT /watchlist/<ticker> — all fields optional"""
    notes: Optional[str] = None
    sector: Optional[str] = None
    tags: Optional[list[str]] = None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        return _clean_tags(v)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.notes is None and self.sector is None and self.tags is None:
            raise ValueError("At least one field (notes, sector, tags) must be provided")
        return self


# ---------------------------------------------------------------------------
# gainers.py
# ---------------------------------------------------------------------------

HeatmapPeriod = Literal["week", "month", "year", "all"]
HeatmapView   = Literal["float_rvol", "sector"]
SortOrder     = Literal["appearances", "avg_gap", "last_seen", "first_seen"]


class GainerFilterQuery(BaseModel):
    """GET /gainers, /gainers/export, /gainers/heatmap"""
    date: Optional[datetime.date] = None
    min_gap: Optional[float] = None
    max_float: Optional[float] = None
    min_rvol: Optional[float] = None
    sector: Optional[str] = None
    # heatmap-specific
    period: HeatmapPeriod = "all"
    view: HeatmapView = "float_rvol"

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if not v:
            return None
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    @field_validator("min_gap", "max_float", "min_rvol", mode="before")
    @classmethod
    def coerce_float(cls, v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            raise ValueError("must be a number")


class TickerHistoryQuery(BaseModel):
    """GET /gainers/ticker-history"""
    period: HeatmapPeriod = "all"
    search: Optional[str] = None
    sort: SortOrder = "last_seen"
    limit: Annotated[int, Field(ge=1, le=500)] = 200
    date: Optional[datetime.date] = None
    min_gap: Optional[float] = None
    max_float: Optional[float] = None
    min_rvol: Optional[float] = None
    sector: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if not v:
            return None
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")

    @field_validator("min_gap", "max_float", "min_rvol", mode="before")
    @classmethod
    def coerce_float(cls, v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            raise ValueError("must be a number")

    @field_validator("limit", mode="before")
    @classmethod
    def coerce_limit(cls, v):
        return int(v) if v is not None else 200

    @field_validator("search", mode="before")
    @classmethod
    def upper_search(cls, v):
        if not v:
            return None
        return str(v).upper().strip()


class PipeScanQuery(BaseModel):
    """GET /gainers/pipe-scan"""
    date: datetime.date

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")


# ---------------------------------------------------------------------------
# charts.py
# ---------------------------------------------------------------------------

class ChartUpdateBody(BaseModel):
    """PUT /charts/<id>"""
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    cleanliness_score: Optional[Annotated[int, Field(ge=1, le=10)]] = None
    setup_type: Optional[str] = None
    timeframe: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("tags must be a list")
        return _clean_tags(v)

    @model_validator(mode="after")
    def at_least_one_field(self):
        fields = [self.notes, self.tags, self.cleanliness_score,
                  self.setup_type, self.timeframe]
        if all(f is None for f in fields):
            raise ValueError("No valid fields to update")
        return self


class ChartUploadForm(BaseModel):
    """POST /charts — validated from request.form (multipart), not JSON."""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    capture_date: datetime.date
    timeframe: Optional[str] = None
    setup_type: Optional[str] = None
    cleanliness_score: Optional[Annotated[int, Field(ge=1, le=10)]] = None
    notes: str = ""
    tags: list[str] = []

    model_config = {"populate_by_name": True}

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("capture_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("capture_date must be in YYYY-MM-DD format")

    @field_validator("cleanliness_score", mode="before")
    @classmethod
    def coerce_score(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            raise ValueError("cleanliness_score must be an integer")

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v):
        """Accept a JSON string (from form-data) or a list."""
        import json as _json
        if isinstance(v, list):
            return _clean_tags(v)
        if isinstance(v, str):
            try:
                parsed = _json.loads(v)
                if not isinstance(parsed, list):
                    raise ValueError
                return _clean_tags(parsed)
            except (ValueError, TypeError):
                raise ValueError("tags must be a JSON array string")
        return []


# ---------------------------------------------------------------------------
# continuation_picks.py
# ---------------------------------------------------------------------------

class SinglePickBody(BaseModel):
    """One continuation pick — used inside PickAddBody."""
    ticker: Annotated[str, Field(min_length=1, max_length=10)]
    date: datetime.date
    reason: Optional[str] = None
    gap_pct: Optional[float] = None
    float_shares: Optional[float] = None
    rvol_15m: Optional[float] = None
    sector: Optional[str] = None
    rank: int = 1

    @field_validator("ticker", mode="before")
    @classmethod
    def normalise_ticker(cls, v):
        return _upper_strip(str(v)) if v else v

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, datetime.date):
            return v
        try:
            return datetime.date.fromisoformat(str(v))
        except ValueError:
            raise ValueError("date must be in YYYY-MM-DD format")


class PickAddBody(BaseModel):
    """POST /continuation-picks — accepts a single pick or a list."""
    picks: Annotated[list[SinglePickBody], Field(min_length=1)]

    @model_validator(mode="before")
    @classmethod
    def wrap_single(cls, v):
        """Allow the client to send either a single object or an array."""
        if isinstance(v, list):
            return {"picks": v}
        if isinstance(v, dict) and "picks" not in v:
            # Single pick sent as a bare object
            return {"picks": [v]}
        return v


# ---------------------------------------------------------------------------
# strategies.py & signals.py — Strategy, backtest, and signal schemas
# ---------------------------------------------------------------------------

class StrategyCreateBody(BaseModel):
    """POST /strategies"""
    name: Annotated[str, Field(min_length=1, max_length=128)]
    description: Optional[str] = None
    version: str = "1.0.0"
    asset_class: Optional[str] = None
    timeframes: Optional[list[str]] = None
    parameters: dict = Field(default_factory=dict)
    is_active: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return str(v).strip() if v else v


class StrategyUpdateBody(BaseModel):
    """PUT /strategies/{id}"""
    name: Optional[Annotated[str, Field(min_length=1, max_length=128)]] = None
    description: Optional[str] = None
    version: Optional[str] = None
    asset_class: Optional[str] = None
    timeframes: Optional[list[str]] = None
    parameters: Optional[dict] = None
    is_active: Optional[bool] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return str(v).strip() if v else v


class BacktestSaveBody(BaseModel):
    """POST /strategies/{id}/backtests"""
    symbol: Annotated[str, Field(min_length=1, max_length=32)]
    timeframe: Annotated[str, Field(min_length=1, max_length=16)]
    start_date: datetime.date
    end_date: datetime.date
    parameters: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)
    trades: Optional[list] = None
    equity_curve: Optional[list] = None
    notes: Optional[str] = None

    @field_validator("symbol", mode="before")
    @classmethod
    def normalise_symbol(cls, v):
        return _upper_strip(str(v)) if v else v


class SignalCreateBody(BaseModel):
    """POST /webhook/signal or POST /signals"""
    symbol: Annotated[str, Field(min_length=1, max_length=32)]
    signal_type: Literal['ENTRY_LONG', 'ENTRY_SHORT', 'EXIT', 'ALERT']
    price: float
    strategy_id: Optional[int] = None
    timeframe: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: Optional[float] = None
    metadata: Optional[dict] = None
    ts: Optional[datetime.datetime] = None

    @field_validator("symbol", mode="before")
    @classmethod
    def normalise_symbol(cls, v):
        return _upper_strip(str(v)) if v else v
