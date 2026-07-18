"""
fastapi_app/tasks/alerts.py

Celery tasks for sending real-time alerts and notifications to external services like Telegram.
These tasks run in a synchronous environment (Celery worker process).
"""
import httpx
from datetime import datetime
import asyncio
import asyncpg
from celery.utils.log import get_task_logger

from fastapi_app.celery_app import celery_app
from fastapi_app.config import settings
from services.alarm_metrics_service import compute_hourly_metrics, compute_daily_rollup, save_alarm_metrics
from validation import EASTERN_TZ

logger = get_task_logger(__name__)


def send_telegram_message(message: str) -> bool:
    """
    Directly sends a raw markdown message to Telegram (synchronous helper).
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not token or not chat_id:
        logger.warning("Telegram bot settings not configured. Skipping raw message dispatch.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        logger.info("Sending Telegram system message...")
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        logger.info("Successfully sent Telegram system message.")
        return True
    except Exception as e:
        logger.error("Failed to send raw Telegram message: %s", e)
        return False


@celery_app.task(name="fastapi_app.tasks.alerts.send_telegram_message_task")
def send_telegram_message_task(message: str) -> dict:
    """
    Celery task wrapper to send a raw markdown message to Telegram.
    """
    success = send_telegram_message(message)
    return {"status": "success" if success else "failed"}


# ── Alert type metadata ────────────────────────────────────────────────────
# Drives the header rendering and which optional fields get shown.
#   signal=None   → no Signal line at all
#   signal=str    → static Signal line, no escaping required
#   signal="auto" → dynamic, escapes the alert_type itself
ALERT_TYPE_META: dict[str, dict] = {
    "VOLATILITY_HALT":     {"emoji": "⏸️",  "header": "VOLATILITY HALT",          "signal": "Volatility Halt (Status H)",        "show_rvol": False},
    "VOLATILITY_RESUME":   {"emoji": "▶️",  "header": "VOLATILITY RESUME",        "signal": "Volatility Resume (Status Active)", "show_rvol": False},
    "NEAR_HOD_RADAR":      {"emoji": "🏔️",  "header": "NEAR HOD RADAR",           "signal": None,                               "show_rvol": True},
    "VOLUME_SPIKE":        {"emoji": "🔊",  "header": "VOLUME SPIKE",             "signal": None,                               "show_rvol": True},
    "PREV_DAY_BREAKOUT":   {"emoji": "🚀",  "header": "PREV DAY HIGH BREAKOUT",   "signal": None,                               "show_rvol": True},
    "VWAP_CROSSOVER":      {"emoji": "🌊",  "header": "VWAP CROSSOVER",           "signal": None,                               "show_rvol": True},
    "VWAP_BOUNCE":         {"emoji": "📈",  "header": "VWAP SUPPORT BOUNCE",      "signal": None,                               "show_rvol": True},
    "RUNNING_UP":          {"emoji": "📈",  "header": "RUNNING UP",               "signal": None,                               "show_rvol": True},
    "BULL_FLAG":           {"emoji": "🚩",  "header": "BULL FLAG",                "signal": None,                               "show_rvol": True},
    "MULTI_TF_CONFLUENCE": {"emoji": "🎯",  "header": "MULTI-TF CONFLUENCE",      "signal": None,                               "show_rvol": True},
    "HALT_RESUME_MOMENTUM": {"emoji": "⚡",  "header": "HALT RESUME MOMENTUM",     "signal": None,                               "show_rvol": True},
}

FALLBACK_META: dict = {"emoji": "🚨", "header": "BREAKOUT DETECTED", "signal": "auto", "show_rvol": True}


# ── Format helpers ─────────────────────────────────────────────────────────
def _escape_markdown(text) -> str:
    """Escape Telegram Markdown special chars: _, *, [, `."""
    if not isinstance(text, str):
        text = str(text)
    for char in ["_", "*", "[", "`"]:
        text = text.replace(char, f"\\{char}")
    return text


def _fmt_volume(v: int) -> str:
    """Format volume as K/M abbreviation."""
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}K"
    return str(v)


def _fmt_cap(cap: float) -> str:
    """Format market cap as M/B."""
    if cap >= 1_000_000_000:
        return f"${cap / 1_000_000_000:.1f}B"
    if cap >= 1_000_000:
        return f"${cap / 1_000_000:.0f}M"
    return f"${cap:,.0f}"


def _fmt_float(shares: int) -> str:
    """Format float shares as M."""
    if shares >= 1_000_000:
        return f"{shares / 1_000_000:.1f}M"
    return f"{shares:,}"


# ── Message builder ────────────────────────────────────────────────────────
def _format_alert_message(alert_data: dict) -> str:
    """
    Build the Markdown body for a single Telegram alert.

    Always renders header + (Ticker, Price, optional Signal, optional RVOL)
    + optional context lines (candle vol, vwap, pdh, float) + Time.
    Optional context lines are empty strings when their source data is
    missing, so they self-guard without an explicit show/hide flag.
    """
    symbol        = alert_data.get("symbol", "UNKNOWN")
    price         = alert_data.get("price", 0.0)
    alert_type    = alert_data.get("alert_type", "Breakout")
    rvol          = alert_data.get("rvol", 0.0)
    timestamp_str = alert_data.get("time", "")
    priority_score = alert_data.get("priority_score", 0)
    priority_tier  = alert_data.get("priority_tier", "Tier 3")
    strategy_label = alert_data.get("strategy_label", "")
    hod_dist       = alert_data.get("hod_dist_pct")
    catalyst       = alert_data.get("catalyst", "")
    stop_price     = alert_data.get("stop_price", 0.0)
    stop_risk_pct  = alert_data.get("stop_risk_pct", 0.0)

    daily_pct      = alert_data.get("daily_pct", 0.0)
    candle_vol     = alert_data.get("candle_vol", 0)
    avg_candle_vol = alert_data.get("avg_candle_vol", 0)
    vwap           = alert_data.get("vwap", 0.0)
    yesterday_high = alert_data.get("yesterday_high", 0.0)
    float_category = alert_data.get("float_category", "")
    market_cap     = alert_data.get("market_cap", 0)
    float_shares   = alert_data.get("float_shares", 0)

    try:
        dt = datetime.fromisoformat(timestamp_str)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        timestamp = timestamp_str

    meta = ALERT_TYPE_META.get(alert_type, FALLBACK_META)

    if meta["signal"] == "auto":
        signal_line = f"- *Signal:* {_escape_markdown(alert_type)}\n"
    elif meta["signal"]:
        signal_line = f"- *Signal:* {meta['signal']}\n"
    else:
        signal_line = ""

    rvol_line = f"- *RVOL:* {rvol:.1f}x\n" if meta["show_rvol"] else ""

    daily_sign     = "+" if daily_pct >= 0 else ""
    escaped_symbol = _escape_markdown(symbol)
    tv_link        = f"https://www.tradingview.com/chart/?symbol={symbol}"

    vwap_line = ""
    if vwap > 0:
        vwap_pct  = ((price - vwap) / vwap) * 100.0
        vwap_sign = "+" if vwap_pct >= 0 else ""
        vwap_line = f"- *VWAP dist:* {vwap_sign}{vwap_pct:.1f}% (VWAP ${vwap:.2f})\n"

    pdh_line = ""
    if yesterday_high > 0:
        pdh_pct  = ((price - yesterday_high) / yesterday_high) * 100.0
        pdh_sign = "+" if pdh_pct >= 0 else ""
        pdh_line = f"- *PDH dist:* {pdh_sign}{pdh_pct:.1f}% (PDH ${yesterday_high:.2f})\n"

    candle_vol_line = ""
    if candle_vol and avg_candle_vol:
        cvol_ratio      = candle_vol / avg_candle_vol if avg_candle_vol > 0 else 0
        candle_vol_line = f"- *Candle vol:* {_fmt_volume(candle_vol)} ({cvol_ratio:.1f}x avg {_fmt_volume(avg_candle_vol)})\n"

    float_line = ""
    if float_shares or float_category:
        float_str = _fmt_float(float_shares) if float_shares else "N/A"
        cat_str   = f" [{float_category}]" if float_category else ""
        cap_str   = f" | Cap: {_fmt_cap(market_cap)}" if market_cap else ""
        float_line = f"- *Float:* {float_str}{cat_str}{cap_str}\n"

    priority_line = f"- *Priority:* {priority_tier} (Score: {priority_score})\n"
    strategy_line = f"- *Strategy:* {strategy_label}\n" if strategy_label else ""
    
    hod_line = ""
    if hod_dist is not None:
        hod_sign = "+" if hod_dist >= 0 else ""
        hod_line = f"- *HOD dist:* {hod_sign}{hod_dist:.1f}%\n"
        
    catalyst_line = f"- *Catalyst:* {catalyst}\n" if catalyst else ""
    stop_line = f"- *Suggested Stop:* ${stop_price:,.2f} ({stop_risk_pct:.1f}% risk)\n" if stop_price > 0 else ""

    return (
        f"{meta['emoji']} *{meta['header']}* {meta['emoji']}\n\n"
        f"- *Ticker:* [${escaped_symbol}]({tv_link})\n"
        f"- *Price:* ${price:,.2f} ({daily_sign}{daily_pct:.1f}% day)\n"
        f"{priority_line}"
        f"{strategy_line}"
        f"{signal_line}"
        f"{rvol_line}"
        f"{candle_vol_line}"
        f"{vwap_line}"
        f"{pdh_line}"
        f"{hod_line}"
        f"{catalyst_line}"
        f"{stop_line}"
        f"{float_line}"
        f"- *Time:* {timestamp}"
    )


@celery_app.task(name="fastapi_app.tasks.alerts.send_telegram_alert_task")
def send_telegram_alert_task(alert_data: dict) -> dict:
    """
    Sends a real-time breakout alert notification to Telegram via Bot API.
    Body formatting is driven by ALERT_TYPE_META; see _format_alert_message.
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not token or not chat_id:
        logger.warning(
            "Telegram bot settings not configured (token or chat_id is empty). "
            "Skipping alert dispatch for %s.",
            alert_data.get("symbol"),
        )
        return {"status": "skipped", "reason": "not_configured"}

    symbol = alert_data.get("symbol", "UNKNOWN")
    message = _format_alert_message(alert_data)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        logger.info("Sending Telegram alert for %s to chat %s...", symbol, chat_id)
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        logger.info("Successfully sent Telegram alert for %s.", symbol)

        # Update screener_alerts.sent = TRUE in database
        alert_db_id = alert_data.get("alert_db_id")
        alert_db_time_str = alert_data.get("alert_db_time")
        if alert_db_id and alert_db_time_str:
            try:
                from database import get_connection
                alert_db_time = datetime.fromisoformat(alert_db_time_str)
                with get_connection() as conn:
                    conn.execute("""
                        UPDATE screener_alerts
                        SET sent = TRUE
                        WHERE id = %s AND alert_time = %s
                    """, (alert_db_id, alert_db_time))
                logger.info("Successfully updated sent status to TRUE for alert id %s.", alert_db_id)
            except Exception as db_err:
                logger.error("Failed to update alert sent status in DB: %s", db_err)

        return {"status": "success", "response": response.json()}
    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error occurred while sending Telegram alert for %s: %s | Response: %s",
            symbol, e, e.response.text,
        )
        raise
    except httpx.RequestError as e:
        logger.error("Request error occurred while sending Telegram alert for %s: %s", symbol, e)
        raise


@celery_app.task(name="fastapi_app.tasks.alerts.run_daily_alarm_metrics_rollup_task")
def run_daily_alarm_metrics_rollup_task(date_str: str = None) -> dict:
    """
    Celery task to run the daily/hourly alarm metrics rollup.
    If date_str is provided (format 'YYYY-MM-DD'), it calculates metrics for that date.
    Otherwise, it defaults to the current date in America/New_York.
    """
    async def _run():
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = datetime.now(EASTERN_TZ).date()

        logger.info("Starting alarm metrics rollup task for date %s", target_date)
        conn = await asyncpg.connect(dsn=settings.asyncpg_dsn)
        try:
            # We calculate metrics for every hour from 0 to 23
            for hour in range(24):
                logger.info("Computing metrics for hour %s on date %s", hour, target_date)
                hourly_metrics = await compute_hourly_metrics(conn, target_date, hour)
                await save_alarm_metrics(conn, hourly_metrics)

            # And then the daily rollup
            logger.info("Computing daily rollup metrics for date %s", target_date)
            daily_metrics = await compute_daily_rollup(conn, target_date)
            await save_alarm_metrics(conn, daily_metrics)

            logger.info("Completed alarm metrics rollup task successfully for date %s", target_date)
            return {"status": "success", "date": str(target_date)}
        except Exception as e:
            logger.error("Error running daily alarm metrics rollup: %s", e)
            raise
        finally:
            await conn.close()

    return asyncio.run(_run())
