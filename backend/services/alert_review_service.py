"""
services/alert_review_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deep module owning the Alert Review post-mortem calculations and grid payloads.

Public surface:
    compute_mfe_mae_for_candles(trigger_price, trigger_time, candles) -> dict
    get_alerts_for_date(db, date_val) -> list[dict]
    get_alert_review_summary(db, date_val) -> dict
    get_alert_review_grid(db, date_val) -> dict
    get_alert_review_detail(db, symbol, date_val) -> dict

Per RFC-001, routers call this module directly without doing business logic or raw SQL.
"""
from __future__ import annotations

import logging
from datetime import date as _date, datetime, timedelta
from typing import Any, Optional

import asyncpg

from services.chart_data_service import _read_db_bars, get_chart_data
from validation import EASTERN_TZ, normalize_ticker

log = logging.getLogger(__name__)


def compute_mfe_mae_for_candles(
    trigger_price: float,
    trigger_time: datetime,
    candles: list[dict],
) -> dict[str, dict[str, float]]:
    """
    Compute Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE)
    for an alert over 5m, 15m, 30m, and EOD time horizons post-trigger.

    Args:
        trigger_price: Price when alert triggered.
        trigger_time: Timestamp of alert trigger (tz-aware).
        candles: List of 1-min candle dicts [{'time': datetime|int, 'open', 'high', 'low', 'close'}, ...]
                 sorted ascending by time.

    Returns:
        Dict mapping horizon ('5m', '15m', '30m', 'eod') to
        {'mfe_pct': float, 'mae_pct': float, 'close_pct': float}
    """
    default_result = {
        "5m": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
        "15m": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
        "30m": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
        "eod": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
    }

    if not trigger_price or trigger_price <= 0 or not candles:
        return default_result

    # Helper to convert candle time to datetime for comparison
    def get_candle_dt(c: dict) -> datetime:
        t = c["time"]
        if isinstance(t, (int, float)):
            dt = datetime.fromtimestamp(t, tz=EASTERN_TZ)
            return dt
        if isinstance(t, datetime):
            if t.tzinfo is None:
                return EASTERN_TZ.localize(t)
            return t.astimezone(EASTERN_TZ)
        return trigger_time

    if trigger_time.tzinfo is None:
        trig_dt = EASTERN_TZ.localize(trigger_time)
    else:
        trig_dt = trigger_time.astimezone(EASTERN_TZ)

    # Filter candles occurring at or after trigger_time
    post_candles = [c for c in candles if get_candle_dt(c) >= trig_dt]
    if not post_candles:
        return default_result

    def calc_window_stats(sub_candles: list[dict]) -> dict[str, float]:
        if not sub_candles:
            return {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0}
        max_high = max(c["high"] for c in sub_candles)
        min_low = min(c["low"] for c in sub_candles)
        last_close = sub_candles[-1]["close"]

        mfe_pct = round(((max_high - trigger_price) / trigger_price) * 100.0, 2)
        mae_pct = round(((min_low - trigger_price) / trigger_price) * 100.0, 2)
        close_pct = round(((last_close - trigger_price) / trigger_price) * 100.0, 2)
        return {"mfe_pct": mfe_pct, "mae_pct": mae_pct, "close_pct": close_pct}

    # Horizons
    dt_5m = trig_dt + timedelta(minutes=5)
    dt_15m = trig_dt + timedelta(minutes=15)
    dt_30m = trig_dt + timedelta(minutes=30)

    candles_5m = [c for c in post_candles if get_candle_dt(c) <= dt_5m]
    candles_15m = [c for c in post_candles if get_candle_dt(c) <= dt_15m]
    candles_30m = [c for c in post_candles if get_candle_dt(c) <= dt_30m]

    return {
        "5m": calc_window_stats(candles_5m if candles_5m else post_candles[:5]),
        "15m": calc_window_stats(candles_15m if candles_15m else post_candles[:15]),
        "30m": calc_window_stats(candles_30m if candles_30m else post_candles[:30]),
        "eod": calc_window_stats(post_candles),
    }


async def get_alerts_for_date(db: asyncpg.Connection, date_val: _date) -> list[dict[str, Any]]:
    """Fetch all screener_alerts for a given date."""
    start_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.min.time()))
    end_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.max.time()))

    try:
        rows = await db.fetch(
            """
            SELECT id, symbol, alert_time, trigger_price, trigger_volume, rel_vol, gap_pct,
                   alert_type, sent, priority_score, priority_tier, vwap_dist_pct,
                   hod_dist_pct, catalyst, stop_price, stop_risk_pct, suppressed_reason, group_id
            FROM screener_alerts
            WHERE alert_time >= $1 AND alert_time <= $2
            ORDER BY alert_time ASC
            """,
            start_dt,
            end_dt,
        )
    except Exception as exc:
        log.error("Failed to fetch screener_alerts for date %s: %s", date_val, exc)
        return []

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "symbol": r["symbol"],
            "alert_time": r["alert_time"].isoformat() if r["alert_time"] else None,
            "trigger_price": r["trigger_price"],
            "trigger_volume": r["trigger_volume"],
            "rel_vol": r["rel_vol"],
            "gap_pct": r["gap_pct"],
            "alert_type": r["alert_type"],
            "sent": r["sent"],
            "priority_score": r["priority_score"],
            "priority_tier": r["priority_tier"],
            "vwap_dist_pct": r["vwap_dist_pct"],
            "hod_dist_pct": r["hod_dist_pct"],
            "catalyst": r["catalyst"],
            "stop_price": r["stop_price"],
            "stop_risk_pct": r["stop_risk_pct"],
            "suppressed_reason": r["suppressed_reason"],
            "group_id": str(r["group_id"]) if r["group_id"] else None,
        })
    return results


async def get_alert_review_summary(db: asyncpg.Connection, date_val: _date) -> dict[str, Any]:
    """Compute page-level summary stats for alert review."""
    alerts = await get_alerts_for_date(db, date_val)
    if not alerts:
        return {
            "date": date_val.isoformat(),
            "total_alerts": 0,
            "unique_symbols": 0,
            "tier_counts": {"Tier 1": 0, "Tier 2": 0, "Tier 3": 0},
            "alert_type_counts": {},
            "suppressed_count": 0,
            "mfe_15m_hit_rate": 0.0,
            "avg_mae_15m": 0.0,
        }

    symbols = {a["symbol"] for a in alerts}
    tier_counts = {"Tier 1": 0, "Tier 2": 0, "Tier 3": 0}
    type_counts: dict[str, int] = {}
    suppressed_count = 0
    mfe_15m_hits = 0
    valid_alerts = 0
    mae_15m_sum = 0.0

    # Compute MFE/MAE per symbol using cached DB bars
    start_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.min.time()))
    end_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.max.time()))

    for sym in symbols:
        db_bars = await _read_db_bars(db, sym, start_dt, end_dt)
        sym_alerts = [a for a in alerts if a["symbol"] == sym]

        for a in sym_alerts:
            t_tier = a.get("priority_tier")
            if t_tier in tier_counts:
                tier_counts[t_tier] += 1

            a_type = a.get("alert_type") or "UNKNOWN"
            type_counts[a_type] = type_counts.get(a_type, 0) + 1

            if a.get("suppressed_reason"):
                suppressed_count += 1
                continue

            if a.get("alert_time") and a.get("trigger_price") and db_bars:
                try:
                    trig_time = datetime.fromisoformat(a["alert_time"])
                except ValueError:
                    continue

                mfe_mae = compute_mfe_mae_for_candles(a["trigger_price"], trig_time, db_bars)
                mfe_15 = mfe_mae["15m"]["mfe_pct"]
                mae_15 = mfe_mae["15m"]["mae_pct"]

                valid_alerts += 1
                if mfe_15 >= 2.0:
                    mfe_15m_hits += 1
                mae_15m_sum += mae_15

    hit_rate = round((mfe_15m_hits / valid_alerts * 100.0), 1) if valid_alerts > 0 else 0.0
    avg_mae = round((mae_15m_sum / valid_alerts), 2) if valid_alerts > 0 else 0.0

    return {
        "date": date_val.isoformat(),
        "total_alerts": len(alerts),
        "unique_symbols": len(symbols),
        "tier_counts": tier_counts,
        "alert_type_counts": type_counts,
        "suppressed_count": suppressed_count,
        "mfe_15m_hit_rate": hit_rate,
        "avg_mae_15m": avg_mae,
    }


async def get_alert_review_grid(db: asyncpg.Connection, date_val: _date) -> dict[str, Any]:
    """
    Build two-section grid payload for /alert-review.
    Section 1: alerted_symbols sorted by best 15m MFE.
    Section 2: remaining_gainers (non-alerted gainers) sorted by gap_pct.
    """
    summary = await get_alert_review_summary(db, date_val)
    all_alerts = await get_alerts_for_date(db, date_val)

    start_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.min.time()))
    end_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.max.time()))

    # Group alerts by symbol
    alert_map: dict[str, list[dict]] = {}
    for a in all_alerts:
        sym = a["symbol"]
        if sym not in alert_map:
            alert_map[sym] = []
        alert_map[sym].append(a)

    alerted_symbols = []
    for sym, s_alerts in alert_map.items():
        db_bars = await _read_db_bars(db, sym, start_dt, end_dt)
        alerts_with_mfe = []
        mfe_15m_list = []

        for a in s_alerts:
            a_copy = dict(a)
            if a.get("alert_time") and a.get("trigger_price") and db_bars:
                try:
                    trig_time = datetime.fromisoformat(a["alert_time"])
                    mfe_mae = compute_mfe_mae_for_candles(a["trigger_price"], trig_time, db_bars)
                    a_copy["mfe_mae"] = mfe_mae
                    mfe_15m_list.append(mfe_mae["15m"]["mfe_pct"])
                except Exception:
                    a_copy["mfe_mae"] = None
            else:
                a_copy["mfe_mae"] = None
            alerts_with_mfe.append(a_copy)

        best_15m_mfe = max(mfe_15m_list) if mfe_15m_list else 0.0
        avg_15m_mfe = round(sum(mfe_15m_list) / len(mfe_15m_list), 2) if mfe_15m_list else 0.0

        first_alert = s_alerts[0]
        alerted_symbols.append({
            "symbol": sym,
            "gap_pct": first_alert.get("gap_pct"),
            "rvol": first_alert.get("rel_vol"),
            "alert_count": len(s_alerts),
            "best_15m_mfe": best_15m_mfe,
            "avg_15m_mfe": avg_15m_mfe,
            "alerts": alerts_with_mfe,
        })

    # Sort alerted symbols by best 15m MFE descending
    alerted_symbols.sort(key=lambda x: x["best_15m_mfe"], reverse=True)

    # Fetch top gainers to find non-alerted gainers
    alerted_set = set(alert_map.keys())
    remaining_gainers = []

    try:
        gainer_rows = await db.fetch(
            """
            SELECT DISTINCT symbol, gap_pct, rel_vol, trigger_price
            FROM screener_alerts
            WHERE alert_time >= $1 AND alert_time <= $2
            """,
            start_dt,
            end_dt,
        )
        for gr in gainer_rows:
            sym = gr["symbol"]
            if sym not in alerted_set:
                remaining_gainers.append({
                    "symbol": sym,
                    "gap_pct": gr["gap_pct"],
                    "rvol": gr["rel_vol"],
                    "alert_count": 0,
                    "best_15m_mfe": 0.0,
                    "avg_15m_mfe": 0.0,
                    "alerts": [],
                })
    except Exception as exc:
        log.error("Failed to query remaining gainers: %s", exc)

    remaining_gainers.sort(key=lambda x: x["gap_pct"] or 0.0, reverse=True)

    return {
        "summary": summary,
        "alerted_symbols": alerted_symbols,
        "remaining_gainers": remaining_gainers,
    }


async def get_alert_review_detail(
    db: asyncpg.Connection, symbol: str, date_val: _date
) -> dict[str, Any]:
    """Fetch full chart data + alerts with MFE/MAE for per-symbol detail page."""
    sym_val = normalize_ticker(symbol)
    start_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.min.time()))
    end_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.max.time()))

    chart_payload = await get_chart_data(db, sym_val, date_val, mini=False)
    db_bars = await _read_db_bars(db, sym_val, start_dt, end_dt)

    all_alerts = await get_alerts_for_date(db, date_val)
    sym_alerts = [a for a in all_alerts if a["symbol"] == sym_val]

    alerts_with_mfe = []
    for a in sym_alerts:
        a_copy = dict(a)
        if a.get("alert_time") and a.get("trigger_price") and db_bars:
            try:
                trig_time = datetime.fromisoformat(a["alert_time"])
                a_copy["mfe_mae"] = compute_mfe_mae_for_candles(a["trigger_price"], trig_time, db_bars)
            except Exception:
                a_copy["mfe_mae"] = None
        else:
            a_copy["mfe_mae"] = None
        alerts_with_mfe.append(a_copy)

    return {
        "symbol": sym_val,
        "date": date_val.isoformat(),
        "chart": chart_payload,
        "alerts": alerts_with_mfe,
    }
