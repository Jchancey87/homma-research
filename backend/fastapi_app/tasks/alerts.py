"""
fastapi_app/tasks/alerts.py

Celery tasks for sending real-time alerts and notifications to external services like Telegram.
These tasks run in a synchronous environment (Celery worker process).
"""
import httpx
from datetime import datetime
from celery.utils.log import get_task_logger

from fastapi_app.celery_app import celery_app
from fastapi_app.config import settings

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


@celery_app.task(name="fastapi_app.tasks.alerts.send_telegram_alert_task")
def send_telegram_alert_task(alert_data: dict) -> dict:
    """
    Sends a real-time breakout alert notification to Telegram via Bot API.
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not token or not chat_id:
        logger.warning(
            "Telegram bot settings not configured (token or chat_id is empty). "
            "Skipping alert dispatch for %s.",
            alert_data.get("symbol")
        )
        return {"status": "skipped", "reason": "not_configured"}

    # Extract alert parameters
    symbol = alert_data.get("symbol", "UNKNOWN")
    price = alert_data.get("price", 0.0)
    alert_type = alert_data.get("alert_type", "Breakout")
    rvol = alert_data.get("rvol", 0.0)
    timestamp_str = alert_data.get("time", "")

    # Clean up and format timestamp
    try:
        dt = datetime.fromisoformat(timestamp_str)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        timestamp = timestamp_str

    # Escape Telegram MarkdownV1 special characters
    def escape_markdown(text: str) -> str:
        if not isinstance(text, str):
            return str(text)
        for char in ["_", "*", "[", "`"]:
            text = text.replace(char, f"\\{char}")
        return text

    escaped_symbol = escape_markdown(symbol)
    escaped_alert_type = escape_markdown(alert_type)

    # Construct the Markdown payload
    if alert_type == "VOLATILITY_HALT":
        message = (
            "⏸️ *VOLATILITY HALT* ⏸️\n\n"
            f"- *Ticker:* [${escaped_symbol}](https://www.tradingview.com/chart/?symbol={symbol})\n"
            f"- *Price:* ${price:,.2f}\n"
            f"- *Signal:* Volatility Halt (Status H)\n"
            f"- *Time:* {timestamp}"
        )
    elif alert_type == "VOLATILITY_RESUME":
        message = (
            "▶️ *VOLATILITY RESUME* ▶️\n\n"
            f"- *Ticker:* [${escaped_symbol}](https://www.tradingview.com/chart/?symbol={symbol})\n"
            f"- *Price:* ${price:,.2f}\n"
            f"- *Signal:* Volatility Resume (Status Active)\n"
            f"- *Time:* {timestamp}"
        )
    elif alert_type == "VOLUME_SPIKE":
        message = (
            "🔊 *VOLUME SPIKE* 🔊\n\n"
            f"- *Ticker:* [${escaped_symbol}](https://www.tradingview.com/chart/?symbol={symbol})\n"
            f"- *Price:* ${price:,.2f}\n"
            f"- *Signal:* 1-Min Volume Spike (>= 5x Avg)\n"
            f"- *Volume ratio:* {rvol}x\n"
            f"- *Time:* {timestamp}"
        )
    elif alert_type == "PREV_DAY_BREAKOUT":
        message = (
            "🚀 *PREV DAY HIGH BREAKOUT* 🚀\n\n"
            f"- *Ticker:* [${escaped_symbol}](https://www.tradingview.com/chart/?symbol={symbol})\n"
            f"- *Price:* ${price:,.2f}\n"
            f"- *Signal:* Previous Day High Breakout\n"
            f"- *Volume ratio:* {rvol}x\n"
            f"- *Time:* {timestamp}"
        )
    elif alert_type == "VWAP_BOUNCE":
        message = (
            "📈 *VWAP SUPPORT BOUNCE* 📈\n\n"
            f"- *Ticker:* [${escaped_symbol}](https://www.tradingview.com/chart/?symbol={symbol})\n"
            f"- *Price:* ${price:,.2f}\n"
            f"- *Signal:* VWAP Support Hold & Bounce\n"
            f"- *Volume ratio:* {rvol}x\n"
            f"- *Time:* {timestamp}"
        )
    else:
        message = (
            "🚨 *BREAKOUT DETECTED* 🚨\n\n"
            f"- *Ticker:* [${escaped_symbol}](https://www.tradingview.com/chart/?symbol={symbol})\n"
            f"- *Price:* ${price:,.2f}\n"
            f"- *Signal:* {escaped_alert_type}\n"
            f"- *Volume ratio:* {rvol}x\n"
            f"- *Time:* {timestamp}"
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        logger.info("Sending Telegram alert for %s to chat %s...", symbol, chat_id)
        response = httpx.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        logger.info("Successfully sent Telegram alert for %s.", symbol)
        return {"status": "success", "response": response.json()}
    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error occurred while sending Telegram alert for %s: %s | Response: %s",
            symbol, e, e.response.text
        )
        raise
    except httpx.RequestError as e:
        logger.error("Request error occurred while sending Telegram alert for %s: %s", symbol, e)
        raise
