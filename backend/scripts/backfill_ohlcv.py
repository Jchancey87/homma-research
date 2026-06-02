"""
scripts/backfill_ohlcv.py
Backfill historical OHLCV data from yfinance into TimescaleDB.

Usage:
    python3 scripts/backfill_ohlcv.py                     # backfill defaults
    python3 scripts/backfill_ohlcv.py --symbols AAPL TSLA # specific symbols
    python3 scripts/backfill_ohlcv.py --daily-only         # skip intraday

Writes to:
    - price_history_daily  (hypertable, up to 5 years)
    - price_history_1min   (hypertable, up to 7 days — yfinance limit)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timezone

# Path bootstrap
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import yfinance as yf
import pandas as pd

from fastapi_app.db.core import create_pool, close_pool, get_pool
from fastapi_app.db.ohlcv import insert_bars_daily, insert_bars_1min

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Default symbols to backfill
DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "META", "AMD", "MSFT"]


def fetch_daily(symbol: str, period: str = "5y") -> list[tuple]:
    """Download daily bars from yfinance and return as list of tuples."""
    log.info("[%s] Downloading daily bars (period=%s)", symbol, period)
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=True, progress=False)

    if df.empty:
        log.warning("[%s] No daily data returned", symbol)
        return []

    # yfinance returns MultiIndex columns when downloading single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    records = []
    for idx, row in df.iterrows():
        dt = idx.date() if hasattr(idx, 'date') else idx
        records.append((
            symbol,
            dt,
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
        ))

    log.info("[%s] Fetched %d daily bars (%s → %s)",
             symbol, len(records),
             records[0][1] if records else "?",
             records[-1][1] if records else "?")
    return records


def fetch_1min(symbol: str, period: str = "7d") -> list[tuple]:
    """Download 1-minute bars from yfinance (max 7 days)."""
    log.info("[%s] Downloading 1-min bars (period=%s)", symbol, period)
    df = yf.download(symbol, period=period, interval="1m", auto_adjust=True, progress=False)

    if df.empty:
        log.warning("[%s] No 1-min data returned", symbol)
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    records = []
    for idx, row in df.iterrows():
        ts = idx.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        records.append((
            symbol,
            ts,
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
        ))

    log.info("[%s] Fetched %d 1-min bars (%s → %s)",
             symbol, len(records),
             records[0][1].strftime("%Y-%m-%d %H:%M") if records else "?",
             records[-1][1].strftime("%Y-%m-%d %H:%M") if records else "?")
    return records


async def backfill_symbol(
    symbol: str,
    daily_period: str = "5y",
    include_1min: bool = True,
) -> dict:
    """Backfill a single symbol and return insert counts."""
    pool = get_pool()
    result = {"symbol": symbol, "daily": 0, "1min": 0}

    # Daily bars
    daily_records = fetch_daily(symbol, period=daily_period)
    if daily_records:
        async with pool.acquire() as conn:
            async with conn.transaction():
                result["daily"] = await insert_bars_daily(conn, daily_records)

    # 1-minute bars (yfinance limits to 7 days)
    if include_1min:
        min_records = fetch_1min(symbol, period="7d")
        if min_records:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    result["1min"] = await insert_bars_1min(conn, min_records)

    return result


async def main(symbols: list[str], daily_period: str, include_1min: bool):
    """Run the full backfill pipeline."""
    log.info("=" * 60)
    log.info("OHLCV Backfill — %d symbols", len(symbols))
    log.info("Daily period: %s | Include 1-min: %s", daily_period, include_1min)
    log.info("=" * 60)

    await create_pool()

    results = []
    for sym in symbols:
        try:
            r = await backfill_symbol(sym, daily_period=daily_period, include_1min=include_1min)
            results.append(r)
        except Exception as exc:
            log.error("[%s] Backfill failed: %s", sym, exc, exc_info=True)

    # Summary
    log.info("")
    log.info("%-8s  %8s  %8s", "Symbol", "Daily", "1-min")
    log.info("-" * 28)
    total_daily, total_1min = 0, 0
    for r in results:
        log.info("%-8s  %8d  %8d", r["symbol"], r["daily"], r["1min"])
        total_daily += r["daily"]
        total_1min += r["1min"]
    log.info("-" * 28)
    log.info("%-8s  %8d  %8d", "TOTAL", total_daily, total_1min)

    # Verify with bar counts
    pool = get_pool()
    async with pool.acquire() as conn:
        from fastapi_app.db.ohlcv import get_bar_counts
        counts = await get_bar_counts(conn)
        log.info("")
        log.info("Database bar counts:")
        for c in counts:
            log.info("  %s %s: %d bars (%s → %s)",
                     c["timeframe"], c["symbol"], c["bar_count"],
                     c["first_date"], c["last_date"])

    await close_pool()
    log.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill OHLCV data from yfinance")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help="Symbols to backfill (default: %(default)s)")
    parser.add_argument("--period", default="5y",
                        help="Daily bar lookback period (default: 5y)")
    parser.add_argument("--daily-only", action="store_true",
                        help="Skip 1-minute data")
    args = parser.parse_args()

    asyncio.run(main(
        symbols=args.symbols,
        daily_period=args.period,
        include_1min=not args.daily_only,
    ))
