"""
fastapi_app/db/strategies.py
CRUD helpers for the strategies and backtest_runs tables.

Tables:
  - strategies    — trading strategy registry
  - backtest_runs — historical backtest results (FK to strategies)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)


def _parse_strategy_row(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    if "parameters" in d and isinstance(d["parameters"], str):
        try:
            d["parameters"] = json.loads(d["parameters"])
        except (ValueError, TypeError):
            pass
    return d


def _parse_backtest_row(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for col in ("parameters", "trades", "equity_curve"):
        if col in d and isinstance(d[col], str):
            try:
                d[col] = json.loads(d[col])
            except (ValueError, TypeError):
                pass
    return d



# ═══════════════════════════════════════════════════════════════════════════
# Strategies
# ═══════════════════════════════════════════════════════════════════════════

async def create_strategy(
    conn: asyncpg.Connection,
    name: str,
    description: Optional[str] = None,
    version: str = "1.0.0",
    asset_class: Optional[str] = None,
    timeframes: Optional[list[str]] = None,
    parameters: Optional[dict] = None,
    is_active: bool = False,
) -> dict:
    """Create a new strategy and return its full record."""
    params_json = json.dumps(parameters) if parameters else "{}"
    row = await conn.fetchrow(
        """
        INSERT INTO strategies
            (name, description, version, asset_class, timeframes, parameters, is_active)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
        RETURNING *
        """,
        name, description, version, asset_class, timeframes, params_json, is_active,
    )
    log.info("[strategies] Created strategy %d: %s", row["id"], name)
    return _parse_strategy_row(row)


async def get_strategy(conn: asyncpg.Connection, strategy_id: int) -> dict | None:
    """Fetch a strategy by ID."""
    row = await conn.fetchrow("SELECT * FROM strategies WHERE id = $1", strategy_id)
    return _parse_strategy_row(row)


async def get_strategy_by_name(conn: asyncpg.Connection, name: str) -> dict | None:
    """Fetch a strategy by unique name."""
    row = await conn.fetchrow("SELECT * FROM strategies WHERE name = $1", name)
    return _parse_strategy_row(row)


async def list_strategies(
    conn: asyncpg.Connection,
    active_only: bool = False,
) -> list[dict]:
    """List all strategies, optionally filtered to active only."""
    if active_only:
        rows = await conn.fetch(
            "SELECT * FROM strategies WHERE is_active = TRUE ORDER BY name"
        )
    else:
        rows = await conn.fetch("SELECT * FROM strategies ORDER BY name")
    return [_parse_strategy_row(r) for r in rows if r is not None]



async def update_strategy(
    conn: asyncpg.Connection,
    strategy_id: int,
    **fields,
) -> dict | None:
    """
    Update a strategy by ID.  Only the provided keyword args are updated.

    Valid fields: name, description, version, asset_class, timeframes,
                  parameters, is_active
    """
    allowed = {
        "name", "description", "version", "asset_class",
        "timeframes", "parameters", "is_active",
    }
    updates, params = [], []
    for key, val in fields.items():
        if key not in allowed:
            continue
        params.append(json.dumps(val) if key == "parameters" else val)
        if key == "parameters":
            updates.append(f"{key} = ${len(params)}::jsonb")
        else:
            updates.append(f"{key} = ${len(params)}")

    if not updates:
        return await get_strategy(conn, strategy_id)

    # Always bump updated_at
    updates.append("updated_at = NOW()")
    params.append(strategy_id)

    row = await conn.fetchrow(
        f"UPDATE strategies SET {', '.join(updates)} "
        f"WHERE id = ${len(params)} RETURNING *",
        *params,
    )
    return _parse_strategy_row(row)


async def delete_strategy(conn: asyncpg.Connection, strategy_id: int) -> bool:
    """Delete a strategy (cascades to backtest_runs)."""
    result = await conn.execute("DELETE FROM strategies WHERE id = $1", strategy_id)
    deleted = result.split()[-1] != "0"
    if deleted:
        log.info("[strategies] Deleted strategy %d", strategy_id)
    return deleted


# ═══════════════════════════════════════════════════════════════════════════
# Backtest Runs
# ═══════════════════════════════════════════════════════════════════════════

async def save_backtest(
    conn: asyncpg.Connection,
    strategy_id: int,
    symbol: str,
    timeframe: str,
    start_date,
    end_date,
    parameters: dict,
    metrics: dict,
    trades: Optional[list] = None,
    equity_curve: Optional[list] = None,
    notes: Optional[str] = None,
) -> int:
    """
    Save a backtest run result and return its ID.

    metrics dict should contain: total_trades, win_rate, profit_factor,
    net_pnl, max_drawdown, sharpe_ratio, sortino_ratio, avg_win, avg_loss
    """
    row = await conn.fetchrow(
        """
        INSERT INTO backtest_runs
            (strategy_id, symbol, timeframe, start_date, end_date, parameters,
             total_trades, win_rate, profit_factor, net_pnl, max_drawdown,
             sharpe_ratio, sortino_ratio, avg_win, avg_loss,
             trades, equity_curve, notes)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb,
                $7, $8, $9, $10, $11, $12, $13, $14, $15,
                $16::jsonb, $17::jsonb, $18)
        RETURNING id
        """,
        strategy_id, symbol, timeframe, start_date, end_date,
        json.dumps(parameters),
        metrics.get("total_trades"),
        metrics.get("win_rate"),
        metrics.get("profit_factor"),
        metrics.get("net_pnl"),
        metrics.get("max_drawdown"),
        metrics.get("sharpe_ratio"),
        metrics.get("sortino_ratio"),
        metrics.get("avg_win"),
        metrics.get("avg_loss"),
        json.dumps(trades) if trades else None,
        json.dumps(equity_curve) if equity_curve else None,
        notes,
    )
    backtest_id = row["id"]
    log.info("[backtest] Saved run %d for strategy %d on %s", backtest_id, strategy_id, symbol)
    return backtest_id


async def get_backtests(
    conn: asyncpg.Connection,
    strategy_id: Optional[int] = None,
    symbol: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Fetch backtest runs, optionally filtered by strategy and/or symbol."""
    conditions, params = [], []

    if strategy_id is not None:
        conditions.append(f"b.strategy_id = ${len(params)+1}")
        params.append(strategy_id)
    if symbol:
        conditions.append(f"b.symbol = ${len(params)+1}")
        params.append(symbol)

    params.append(limit)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(
        f"""
        SELECT b.*, s.name AS strategy_name
        FROM backtest_runs b
        LEFT JOIN strategies s ON b.strategy_id = s.id
        {where}
        ORDER BY b.run_at DESC
        LIMIT ${len(params)}
        """,
        *params,
    )
    return [_parse_backtest_row(r) for r in rows if r is not None]


async def get_backtest_by_id(
    conn: asyncpg.Connection,
    backtest_id: int,
) -> dict | None:
    """Fetch a single backtest run by ID with strategy name."""
    row = await conn.fetchrow(
        """
        SELECT b.*, s.name AS strategy_name
        FROM backtest_runs b
        LEFT JOIN strategies s ON b.strategy_id = s.id
        WHERE b.id = $1
        """,
        backtest_id,
    )
    return _parse_backtest_row(row)
