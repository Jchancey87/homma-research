"""
services/alert_review_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deep module owning the Alert Review post-mortem calculations for Top 10 Gainers.

Filtering rules:
  1. Exclude NEAR_HOD and NEAR_HOD_RADAR alert types.
  2. Restrict scope strictly to Top 10 Gainers for the date.

Public surface:
    compute_mfe_mae_for_candles(trigger_price, trigger_time, candles) -> dict
    get_alerts_for_date(db, date_val) -> list[dict]
    get_alert_review_summary(db, date_val) -> dict
    get_alert_review_top10(db, date_val) -> dict
    get_alert_review_detail(db, symbol, date_val) -> dict
"""
from __future__ import annotations

import logging
from datetime import date as _date, datetime, timedelta
from typing import Any, Optional

import asyncpg

from services.chart_data_service import _read_db_bars, get_chart_data
from validation import EASTERN_TZ, normalize_ticker

log = logging.getLogger(__name__)

EXCLUDED_ALERT_TYPES = {"NEAR_HOD", "NEAR_HOD_RADAR"}


def compute_mfe_mae_for_candles(
    trigger_price: float,
    trigger_time: datetime,
    candles: list[dict],
) -> dict[str, dict[str, float]]:
    """
    Compute Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE)
    for an alert over 5m, 15m, 30m, and EOD time horizons post-trigger.
    """
    default_result = {
        "5m": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
        "15m": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
        "30m": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
        "eod": {"mfe_pct": 0.0, "mae_pct": 0.0, "close_pct": 0.0},
    }

    if not trigger_price or trigger_price <= 0 or not candles:
        return default_result

    def get_candle_dt(c: dict) -> datetime:
        t = c["time"]
        if isinstance(t, (int, float)):
            return datetime.fromtimestamp(t, tz=EASTERN_TZ)
        if isinstance(t, datetime):
            if t.tzinfo is None:
                return EASTERN_TZ.localize(t)
            return t.astimezone(EASTERN_TZ)
        return trigger_time

    if trigger_time.tzinfo is None:
        trig_dt = EASTERN_TZ.localize(trigger_time)
    else:
        trig_dt = trigger_time.astimezone(EASTERN_TZ)

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
    """Fetch screener_alerts for a date, excluding NEAR_HOD radar pings."""
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
              AND alert_type NOT IN ('NEAR_HOD', 'NEAR_HOD_RADAR')
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


async def get_top10_gainer_symbols(db: asyncpg.Connection, date_val: _date) -> list[dict[str, Any]]:
    """Retrieve top 10 gainers for date_val."""
    from fastapi_app.db.daily_gainers import top_gainers_on_date
    try:
        dg_rows = await top_gainers_on_date(db, date_val, limit=10)
        if dg_rows:
            return [
                {
                    "symbol": r["ticker"],
                    "gap_pct": r.get("gap_pct"),
                    "rvol": r.get("rvol_15m"),
                }
                for r in dg_rows
            ]
    except Exception as exc:
        log.error("Failed to query top_gainers_on_date: %s", exc)

    # Fallback: query screener_alerts for top 10 symbols by gap_pct
    start_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.min.time()))
    end_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.max.time()))
    try:
        rows = await db.fetch(
            """
            SELECT symbol, MAX(gap_pct) as gap_pct, MAX(rel_vol) as rvol
            FROM screener_alerts
            WHERE alert_time >= $1 AND alert_time <= $2
            GROUP BY symbol
            ORDER BY gap_pct DESC NULLS LAST
            LIMIT 10
            """,
            start_dt,
            end_dt,
        )
        return [{"symbol": r["symbol"], "gap_pct": r["gap_pct"], "rvol": r["rvol"]} for r in rows]
    except Exception as exc:
        log.error("Failed to fallback query top 10 symbols from alerts: %s", exc)

    return []


async def get_alert_review_summary(db: asyncpg.Connection, date_val: _date) -> dict[str, Any]:
    """Compute summary stats restricted strictly to Top 10 Gainers."""
    top10 = await get_top10_gainer_symbols(db, date_val)
    top10_symbols = {t["symbol"] for t in top10}

    all_alerts = await get_alerts_for_date(db, date_val)
    top10_alerts = [a for a in all_alerts if a["symbol"] in top10_symbols]

    if not top10_alerts:
        return {
            "date": date_val.isoformat(),
            "total_alerts": 0,
            "unique_symbols": len(top10_symbols),
            "tier_counts": {"Tier 1": 0, "Tier 2": 0, "Tier 3": 0},
            "alert_type_counts": {},
            "suppressed_count": 0,
            "mfe_15m_hit_rate": 0.0,
            "avg_mae_15m": 0.0,
        }

    tier_counts = {"Tier 1": 0, "Tier 2": 0, "Tier 3": 0}
    type_counts: dict[str, int] = {}
    suppressed_count = 0
    mfe_15m_hits = 0
    valid_alerts = 0
    mae_15m_sum = 0.0

    start_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.min.time()))
    end_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.max.time()))

    for sym in top10_symbols:
        db_bars = await _read_db_bars(db, sym, start_dt, end_dt)
        sym_alerts = [a for a in top10_alerts if a["symbol"] == sym]

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
        "total_alerts": len(top10_alerts),
        "unique_symbols": len(top10_symbols),
        "tier_counts": tier_counts,
        "alert_type_counts": type_counts,
        "suppressed_count": suppressed_count,
        "mfe_15m_hit_rate": hit_rate,
        "avg_mae_15m": avg_mae,
    }


async def get_alert_review_top10(db: asyncpg.Connection, date_val: _date) -> dict[str, Any]:
    """Payload for top 10 gainers alert review."""
    summary = await get_alert_review_summary(db, date_val)
    top10_gainers = await get_top10_gainer_symbols(db, date_val)
    all_alerts = await get_alerts_for_date(db, date_val)

    start_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.min.time()))
    end_dt = EASTERN_TZ.localize(datetime.combine(date_val, datetime.max.time()))

    alert_map: dict[str, list[dict]] = {}
    for a in all_alerts:
        sym = a["symbol"]
        if sym not in alert_map:
            alert_map[sym] = []
        alert_map[sym].append(a)

    result_items = []
    for item in top10_gainers:
        sym = item["symbol"]
        s_alerts = alert_map.get(sym, [])

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

        result_items.append({
            "symbol": sym,
            "gap_pct": item.get("gap_pct"),
            "rvol": item.get("rvol"),
            "alert_count": len(s_alerts),
            "best_15m_mfe": best_15m_mfe,
            "avg_15m_mfe": avg_15m_mfe,
            "alerts": alerts_with_mfe,
        })

    return {
        "summary": summary,
        "top10_gainers": result_items,
    }


async def get_alert_review_detail(
    db: asyncpg.Connection, symbol: str, date_val: _date
) -> dict[str, Any]:
    """Fetch full chart data + non-NEAR_HOD alerts with MFE/MAE for detail view."""
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
