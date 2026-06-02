"""
fastapi_app/routers/market_data.py
Router exposing endpoints for time-series data (OHLCV, indicators, signals).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_db
from ..db import ohlcv as db_ohlcv
from ..db import indicators as db_indicators
from ..db import signals as db_signals
from ..db import strategies as db_strategies
from validation.schemas import SignalCreateBody

log = logging.getLogger(__name__)
router = APIRouter(tags=["market_data"])


# ═══════════════════════════════════════════════════════════════════════════
# Helpers for parameter parsing
# ═══════════════════════════════════════════════════════════════════════════

def parse_date_param(val: str | None, default: date) -> date:
    if not val:
        return default
    try:
        return date.fromisoformat(val)
    except ValueError:
        try:
            return datetime.fromisoformat(val).date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {val}. Use YYYY-MM-DD.")


def parse_datetime_param(val: str | None, default: datetime) -> datetime:
    if not val:
        return default
    try:
        # Handle 'Z' suffix for UTC if present
        clean_val = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {val}. Use ISO 8601 format.")


# ═══════════════════════════════════════════════════════════════════════════
# OHLCV Endpoints
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/ohlcv/{symbol}")
async def get_ohlcv(
    symbol: str,
    timeframe: str = "daily",  # 'daily', '1D', '1min', '1m'
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: Optional[int] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Fetch OHLCV candle data for a ticker.
    Supports 'daily' (from price_history_daily) and '1min'/'1m' (from price_history_1min).
    """
    symbol = symbol.upper().strip()
    is_daily = timeframe.lower() in ("daily", "1d")

    if is_daily:
        end_date = parse_date_param(end, datetime.now(timezone.utc).date())
        start_date = parse_date_param(start, end_date - timedelta(days=365))
        limit_val = limit or 1000

        try:
            bars = await db_ohlcv.get_bars_daily(db, symbol, start_date, end_date, limit=limit_val)
            return bars
        except Exception as exc:
            log.error("Failed to fetch daily bars: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))
    else:
        end_dt = parse_datetime_param(end, datetime.now(timezone.utc))
        start_dt = parse_datetime_param(start, end_dt - timedelta(days=7))
        limit_val = limit or 50000

        try:
            bars = await db_ohlcv.get_bars_1min(db, symbol, start_dt, end_dt, limit=limit_val)
            return bars
        except Exception as exc:
            log.error("Failed to fetch 1min bars: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))


@router.get("/ohlcv/{symbol}/resample")
async def resample_ohlcv(
    symbol: str,
    bucket: str = Query(..., description="Postgres interval string, e.g. '5 minutes', '1 hour', '1 day'"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Resample 1-minute historical data into higher timeframes on the fly
    using TimescaleDB's native time_bucket() functionality.
    """
    symbol = symbol.upper().strip()
    now = datetime.now(timezone.utc)
    start_dt = parse_datetime_param(start, now - timedelta(days=7))
    end_dt = parse_datetime_param(end, now)

    try:
        bars = await db_ohlcv.resample_1min(db, symbol, bucket, start_dt, end_dt)
        return bars
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        log.error("Failed to resample 1min bars: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# Technical Indicators
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/indicators/{symbol}")
async def get_indicators(
    symbol: str,
    timeframe: str = "1min",
    indicator_name: Optional[str] = None,
    indicator_names: Optional[list[str]] = Query(None),
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 1000,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Fetch stored technical indicators for a ticker.
    Can request a single indicator name or multiple using query params.
    """
    symbol = symbol.upper().strip()
    now = datetime.now(timezone.utc)
    start_dt = parse_datetime_param(start, now - timedelta(days=7))
    end_dt = parse_datetime_param(end, now)

    try:
        if indicator_names:
            rows = await db_indicators.get_indicators_multi(
                db, symbol, indicator_names, timeframe, start_dt, end_dt
            )
            return rows
        elif indicator_name:
            rows = await db_indicators.get_indicator(
                db, symbol, indicator_name, timeframe, start_dt, end_dt, limit=limit
            )
            return rows
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'indicator_name' or 'indicator_names' query parameter must be provided."
            )
    except Exception as exc:
        log.error("Failed to fetch indicators: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ═══════════════════════════════════════════════════════════════════════════
# Trading Signals & Webhooks
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/signals")
async def list_global_signals(
    symbol: Optional[str] = None,
    signal_type: Optional[str] = None,
    strategy_id: Optional[int] = None,
    limit: int = 50,
    db: asyncpg.Connection = Depends(get_db),
):
    """Fetch trading signals globally across all symbols, with optional filtering."""
    try:
        signals = await db_signals.get_signals(
            db, symbol=symbol, limit=limit, signal_type=signal_type, strategy_id=strategy_id
        )
        return signals
    except Exception as exc:
        log.error("Failed to list global signals: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/signals/{symbol}")
async def list_signals(
    symbol: str,
    signal_type: Optional[str] = None,
    strategy_id: Optional[int] = None,
    limit: int = 50,
    db: asyncpg.Connection = Depends(get_db),
):
    """Fetch trading signals for a ticker with optional type and strategy filters."""
    symbol = symbol.upper().strip()
    try:
        signals = await db_signals.get_signals(
            db, symbol, limit=limit, signal_type=signal_type, strategy_id=strategy_id
        )
        return signals
    except Exception as exc:
        log.error("Failed to list signals: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/signals", status_code=201)
@router.post("/webhook/signal", status_code=201)
async def create_signal(
    body: SignalCreateBody,
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Ingest a new trading signal.
    Accepts manual entries or webhooks from external engines (e.g. TradingView).
    """
    if body.strategy_id is not None:
        strat = await db_strategies.get_strategy(db, body.strategy_id)
        if not strat:
            raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        signal_id = await db_signals.insert_signal(
            db,
            symbol=body.symbol,
            signal_type=body.signal_type,
            price=body.price,
            strategy_id=body.strategy_id,
            timeframe=body.timeframe,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            confidence=body.confidence,
            metadata=body.metadata,
            ts=body.ts,
        )
        return {"id": signal_id}
    except Exception as exc:
        log.error("Failed to create signal: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
