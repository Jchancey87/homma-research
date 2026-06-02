"""
fastapi_app/db/ — Database access layer package.

Re-exports from the base db module so existing imports continue to work,
and provides domain-specific modules for time-series and relational data:

  - db.ohlcv       — price_history_1min / price_history_daily read/write
  - db.indicators   — computed indicator values (hypertable)
  - db.signals      — strategy-generated trade signals
  - db.strategies   — strategy CRUD + backtest_runs
"""

# Re-export everything from the base db module so that
# `from ..db import get_db, rows_to_list, row_to_dict` still works
# when __init__.py is present (package mode).
from fastapi_app.db.core import (   # noqa: F401
    create_pool,
    close_pool,
    get_pool,
    get_db,
    row_to_dict,
    rows_to_list,
    check_db_health,
)
