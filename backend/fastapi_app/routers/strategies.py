"""
fastapi_app/routers/strategies.py
Router exposing endpoints for strategy registration and backtest results.
"""
from __future__ import annotations

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..db import strategies as db_strategies
from validation.schemas import StrategyCreateBody, StrategyUpdateBody, BacktestSaveBody

log = logging.getLogger(__name__)
router = APIRouter(prefix="/strategies", tags=["strategies"])


# ═══════════════════════════════════════════════════════════════════════════
# Strategies CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("", status_code=201)
async def create_strategy(
    body: StrategyCreateBody,
    db: asyncpg.Connection = Depends(get_db),
):
    """Register a new strategy in the database."""
    existing = await db_strategies.get_strategy_by_name(db, body.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Strategy with name '{body.name}' already exists."
        )

    try:
        strat = await db_strategies.create_strategy(
            db,
            name=body.name,
            description=body.description,
            version=body.version,
            asset_class=body.asset_class,
            timeframes=body.timeframes,
            parameters=body.parameters,
            is_active=body.is_active,
        )
        return strat
    except Exception as exc:
        log.error("Failed to create strategy: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("")
async def list_strategies(
    active_only: bool = False,
    db: asyncpg.Connection = Depends(get_db),
):
    """Retrieve all strategies, optionally filtering to active ones."""
    try:
        strats = await db_strategies.list_strategies(db, active_only=active_only)
        return strats
    except Exception as exc:
        log.error("Failed to list strategies: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: int,
    db: asyncpg.Connection = Depends(get_db),
):
    """Get a strategy's metadata by ID."""
    strat = await db_strategies.get_strategy(db, strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strat


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: int,
    body: StrategyUpdateBody,
    db: asyncpg.Connection = Depends(get_db),
):
    """Update a strategy by ID. Only provided fields will be modified."""
    existing = await db_strategies.get_strategy(db, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")

    update_fields = body.model_dump(exclude_unset=True)
    if not update_fields:
        return existing

    # If updating the name, check for duplicates
    if "name" in update_fields and update_fields["name"] != existing["name"]:
        dup = await db_strategies.get_strategy_by_name(db, update_fields["name"])
        if dup:
            raise HTTPException(
                status_code=409,
                detail=f"Strategy with name '{update_fields['name']}' already exists."
            )

    try:
        strat = await db_strategies.update_strategy(db, strategy_id, **update_fields)
        return strat
    except Exception as exc:
        log.error("Failed to update strategy %d: %s", strategy_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    db: asyncpg.Connection = Depends(get_db),
):
    """Delete a strategy and all cascading backtest runs."""
    ok = await db_strategies.delete_strategy(db, strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════════════════
# Backtest Results
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/{strategy_id}/backtests", status_code=201)
async def save_backtest(
    strategy_id: int,
    body: BacktestSaveBody,
    db: asyncpg.Connection = Depends(get_db),
):
    """Save a new backtest run result for the given strategy."""
    strat = await db_strategies.get_strategy(db, strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        backtest_id = await db_strategies.save_backtest(
            db,
            strategy_id=strategy_id,
            symbol=body.symbol,
            timeframe=body.timeframe,
            start_date=body.start_date,
            end_date=body.end_date,
            parameters=body.parameters,
            metrics=body.metrics,
            trades=body.trades,
            equity_curve=body.equity_curve,
            notes=body.notes,
        )
        return {"id": backtest_id}
    except Exception as exc:
        log.error("Failed to save backtest for strategy %d: %s", strategy_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{strategy_id}/backtests")
async def list_strategy_backtests(
    strategy_id: int,
    symbol: Optional[str] = None,
    limit: int = 50,
    db: asyncpg.Connection = Depends(get_db),
):
    """List recent backtest runs for the strategy, optionally filtering by symbol."""
    strat = await db_strategies.get_strategy(db, strategy_id)
    if not strat:
        raise HTTPException(status_code=404, detail="Strategy not found")

    try:
        runs = await db_strategies.get_backtests(
            db, strategy_id=strategy_id, symbol=symbol, limit=limit
        )
        return runs
    except Exception as exc:
        log.error("Failed to list backtests for strategy %d: %s", strategy_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/backtests/{backtest_id}")
async def get_backtest_run(
    backtest_id: int,
    db: asyncpg.Connection = Depends(get_db),
):
    """Get a detailed backtest run by ID."""
    run = await db_strategies.get_backtest_by_id(db, backtest_id)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run
