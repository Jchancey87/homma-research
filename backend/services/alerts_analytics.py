"""
services/alerts_analytics.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deep module that owns the alert analytics pipeline.

Two public async functions consumed by routers/alerts.py:

    compute_daily_summary(db, target_date=None) -> dict
    compute_performance_scorecard(db, days) -> dict

Both delegate I/O to the DB and pure transforms to small helpers that can
be unit-tested without an HTTP layer.

Originally extracted from routers/alerts.py:85-220 and 255-369 (RFC-001).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date as _date, datetime
from typing import Optional

import asyncpg
import pytz

log = logging.getLogger(__name__)

EASTERN = pytz.timezone("America/New_York")
PRICE_BUCKETS = ((2, "$1-2"), (5, "$2-5"), (15, "$5-15"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def compute_daily_summary(
    db: asyncpg.Connection, target_date: Optional[_date] = None
) -> dict:
    """
    Get all alerts for a specific US/Eastern date, joined with stock
    fundamentals, augmented with forward returns (1m/3m/5m/15m, MFE, MAE),
    and grouped by ticker symbol.

    If target_date is None, the most recent alert date in the DB is used;
    if no alerts exist, today (US/Eastern) is returned with an empty list.
    """
    if target_date is None:
        target_date = await _latest_alert_date(db) or datetime.now(EASTERN).date()

    rows = await db.fetch(
        """
        SELECT a.id, a.symbol, a.alert_time, a.trigger_price, a.trigger_volume,
               a.rel_vol, a.gap_pct, a.float_shares, a.alert_type, a.sent,
               a.feedback_score, a.feedback_notes,
               f.company_name, f.float_category, f.market_cap
        FROM public.screener_alerts a
        LEFT JOIN public.stock_fundamentals f ON a.symbol = f.symbol
        WHERE (a.alert_time AT TIME ZONE 'America/New_York')::date = $1
        ORDER BY a.symbol, a.alert_time ASC
        """,
        target_date,
    )

    fwd_by_id = await _forward_returns_for_alerts(db, rows)
    tickers = _group_alerts_by_ticker(rows, fwd_by_id)

    return {"date": target_date.isoformat(), "tickers": tickers}


async def compute_performance_scorecard(db: asyncpg.Connection, days: int) -> dict:
    """
    Statistical performance scorecard for screener alerts.

    Returns win rates, expectancy, and average forward returns grouped by:
      - alert_type
      - price_bucket ($1-2, $2-5, $5-15, $15+)
      - float_category

    Only alerts with 5-minute forward return data are counted.
    """
    rows = await db.fetch(
        """
        WITH alert_fwd AS (
            SELECT
                a.id,
                a.alert_type,
                a.trigger_price,
                f.float_category,
                CASE
                    WHEN a.trigger_price < 2   THEN '$1-2'
                    WHEN a.trigger_price < 5   THEN '$2-5'
                    WHEN a.trigger_price < 15  THEN '$5-15'
                    ELSE '$15+'
                END AS price_bucket,
                (
                    SELECT (ph.close - a.trigger_price) / a.trigger_price * 100.0
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time + INTERVAL '4 minutes 30 seconds'
                      AND ph.timestamp <= a.alert_time + INTERVAL '5 minutes 30 seconds'
                    ORDER BY ph.timestamp ASC
                    LIMIT 1
                ) AS fwd_5m,
                (
                    SELECT (ph.close - a.trigger_price) / a.trigger_price * 100.0
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time + INTERVAL '14 minutes 30 seconds'
                      AND ph.timestamp <= a.alert_time + INTERVAL '15 minutes 30 seconds'
                    ORDER BY ph.timestamp ASC
                    LIMIT 1
                ) AS fwd_15m,
                (
                    SELECT MAX(ph.high)
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time
                      AND ph.timestamp <= a.alert_time + INTERVAL '15 minutes'
                ) AS mfe_high,
                (
                    SELECT MIN(ph.low)
                    FROM price_history_1min ph
                    WHERE ph.symbol = a.symbol
                      AND ph.timestamp >= a.alert_time
                      AND ph.timestamp <= a.alert_time + INTERVAL '15 minutes'
                ) AS mae_low
            FROM public.screener_alerts a
            LEFT JOIN public.stock_fundamentals f ON a.symbol = f.symbol
            WHERE a.alert_time >= NOW() - ($1 || ' days')::INTERVAL
              AND a.trigger_price > 0
        )
        SELECT
            alert_type,
            price_bucket,
            float_category,
            COUNT(*) FILTER (WHERE fwd_5m IS NOT NULL) AS sample_count,
            ROUND(AVG(fwd_5m) FILTER (WHERE fwd_5m IS NOT NULL)::numeric, 2) AS avg_fwd_5m,
            ROUND(AVG(fwd_15m) FILTER (WHERE fwd_15m IS NOT NULL)::numeric, 2) AS avg_fwd_15m,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE fwd_5m IS NOT NULL AND fwd_5m > 0)
                / NULLIF(COUNT(*) FILTER (WHERE fwd_5m IS NOT NULL), 0),
                1
            ) AS win_rate_5m_pct,
            ROUND(
                AVG(
                    CASE WHEN mfe_high IS NOT NULL AND trigger_price > 0
                         THEN (mfe_high - trigger_price) / trigger_price * 100.0
                    END
                )::numeric, 2
            ) AS avg_mfe_pct,
            ROUND(
                AVG(
                    CASE WHEN mae_low IS NOT NULL AND trigger_price > 0
                         THEN (mae_low - trigger_price) / trigger_price * 100.0
                    END
                )::numeric, 2
            ) AS avg_mae_pct
        FROM alert_fwd
        GROUP BY alert_type, price_bucket, float_category
        ORDER BY alert_type, price_bucket, float_category
        """,
        str(days),
    )

    return {
        "days": days,
        "scorecard": [_scorecard_row(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Latest-alert-date helper
# ---------------------------------------------------------------------------

async def _latest_alert_date(db: asyncpg.Connection) -> Optional[_date]:
    row = await db.fetchrow(
        """
        SELECT (alert_time AT TIME ZONE 'America/New_York')::date AS last_date
        FROM public.screener_alerts
        ORDER BY alert_time DESC
        LIMIT 1
        """
    )
    if row and row["last_date"]:
        return row["last_date"]
    return None


# ---------------------------------------------------------------------------
# Forward returns (async I/O + pure transform split for testability)
# ---------------------------------------------------------------------------

async def _forward_returns_for_alerts(
    db: asyncpg.Connection, rows: list
) -> dict:
    """Fan out candle fetches and return {alert_id: {fwd_*, mfe, mae}}."""
    import asyncio

    fwd_results = await asyncio.gather(*[
        _fetch_alert_forward_returns(
            db,
            r["id"],
            r["symbol"],
            r["alert_time"],
            float(r["trigger_price"] or 0),
        )
        for r in rows
    ])
    return {rows[i]["id"]: fwd_results[i] for i in range(len(rows))}


async def _fetch_alert_forward_returns(
    db: asyncpg.Connection,
    alert_id: int,
    symbol: str,
    alert_time,
    trigger_price: float,
) -> dict:
    """Fetch 1-min candles for the 16m window after an alert and compute fwd returns."""
    try:
        candles = await db.fetch(
            """
            SELECT timestamp, open, high, low, close
            FROM price_history_1min
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp <= $2 + INTERVAL '16 minutes'
            ORDER BY timestamp ASC
            """,
            symbol,
            alert_time,
        )
    except Exception as exc:
        log.warning("Forward return calc failed for alert %s: %s", alert_id, exc)
        return {}
    return _forward_returns_from_candles(trigger_price, candles)


def _forward_returns_from_candles(trigger_price: float, candles: list) -> dict:
    """
    Pure: compute 1m/3m/5m/15m forward returns plus MFE/MAE from 1-min candles.

    trigger_price > 0 required; otherwise returns {}.
    """
    if not candles or trigger_price <= 0:
        return {}

    results: dict = {}
    highs: list = []
    lows: list = []
    for i, c in enumerate(candles):
        highs.append(float(c["high"]))
        lows.append(float(c["low"]))
        close = float(c["close"])
        ret = (close - trigger_price) / trigger_price * 100.0
        minute = i + 1
        if minute == 1:
            results["fwd_1m"] = round(ret, 2)
        elif minute == 3:
            results["fwd_3m"] = round(ret, 2)
        elif minute == 5:
            results["fwd_5m"] = round(ret, 2)
        elif minute == 15:
            results["fwd_15m"] = round(ret, 2)

    if highs:
        results["mfe"] = round((max(highs) - trigger_price) / trigger_price * 100.0, 2)
    if lows:
        results["mae"] = round((min(lows) - trigger_price) / trigger_price * 100.0, 2)

    return results


# ---------------------------------------------------------------------------
# Ticker grouping (pure)
# ---------------------------------------------------------------------------

def _group_alerts_by_ticker(rows: list, fwd_by_id: dict) -> list[dict]:
    """
    Pure: collapse alert rows by symbol and merge forward returns into each alert.
    Returns a list of ticker-group dicts in first-seen order.
    """
    ticker_groups: dict = defaultdict(lambda: {
        "symbol": "",
        "company_name": None,
        "float_category": None,
        "float_shares": None,
        "market_cap": None,
        "gap_pct": None,
        "rvol": None,
        "alerts": [],
    })

    for r in rows:
        sym = r["symbol"]
        group = ticker_groups[sym]
        if not group["symbol"]:
            group["symbol"] = sym
            group["company_name"] = r.get("company_name")
            group["float_category"] = r.get("float_category")
            group["float_shares"] = r.get("float_shares")
            group["market_cap"] = r.get("market_cap")
            group["gap_pct"] = r.get("gap_pct")
            group["rvol"] = r.get("rel_vol")

        fwd = fwd_by_id.get(r["id"], {})
        group["alerts"].append({
            "id": r["id"],
            "alert_time": r["alert_time"].isoformat(),
            "trigger_price": r["trigger_price"],
            "trigger_volume": r["trigger_volume"],
            "rel_vol": r["rel_vol"],
            "alert_type": r["alert_type"],
            "feedback_score": r.get("feedback_score"),
            "feedback_notes": r.get("feedback_notes"),
            "fwd_1m": fwd.get("fwd_1m"),
            "fwd_3m": fwd.get("fwd_3m"),
            "fwd_5m": fwd.get("fwd_5m"),
            "fwd_15m": fwd.get("fwd_15m"),
            "mfe": fwd.get("mfe"),
            "mae": fwd.get("mae"),
        })

    return list(ticker_groups.values())


# ---------------------------------------------------------------------------
# Scorecard row mapping (pure)
# ---------------------------------------------------------------------------

def _scorecard_row(r) -> dict:
    def _f(v):
        return float(v) if v is not None else None
    return {
        "alert_type": r["alert_type"],
        "price_bucket": r["price_bucket"],
        "float_category": r["float_category"],
        "sample_count": r["sample_count"],
        "avg_fwd_5m": _f(r["avg_fwd_5m"]),
        "avg_fwd_15m": _f(r["avg_fwd_15m"]),
        "win_rate_5m_pct": _f(r["win_rate_5m_pct"]),
        "avg_mfe_pct": _f(r["avg_mfe_pct"]),
        "avg_mae_pct": _f(r["avg_mae_pct"]),
    }
