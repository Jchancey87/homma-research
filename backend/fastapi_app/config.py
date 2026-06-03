"""
fastapi_app/config.py
Self-contained settings for the FastAPI layer.

Reads the same environment variables as backend/config.py so both servers
share a single .env / environment — no circular import possible since we
don't import backend/config.py directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # honours the nearest .env file


class Settings:
    # ── Database ────────────────────────────────────────────────────────────
    # asyncpg wants  postgresql://  (NOT postgresql+asyncpg://)
    # Also strip any query params — asyncpg uses keyword args, not DSN params.
    _raw_db_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://journal:journal1@192.168.0.201:5432/trading_journal",
    )
    asyncpg_dsn: str = (
        _raw_db_url
        .replace("postgresql+asyncpg://", "postgresql://")
        .split("?")[0]   # strip ?sslmode=... — asyncpg uses ssl=False kwarg
    )

    # ── App meta ─────────────────────────────────────────────────────────────
    app_title: str = "Homma Research API"
    app_version: str = "2.0.0"
    cors_origins: list[str] = ["*"]  # tighten in production

    _raw_storage: str = os.getenv("STORAGE_PATH", "../storage/charts")
    storage_path: str = (
        os.path.normpath(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                _raw_storage
            )
        )
        if not os.path.isabs(_raw_storage)
        else _raw_storage
    )
    allowed_mime_types: frozenset = frozenset(
        {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    )
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_extensions: frozenset = frozenset({"png", "jpg", "jpeg", "webp"})

    # ── External APIs (forwarded from env so routers can use them) ──────────
    polygon_api_key: str    = os.getenv("POLYGON_API_KEY", "")
    fmp_api_key: str        = os.getenv("FMP_API_KEY", "")
    schwab_api_key: str     = os.getenv("SCHWAB_API_KEY", "")
    schwab_api_secret: str  = os.getenv("SCHWAB_API_SECRET", "")
    schwab_token_path: str  = os.getenv(
        "SCHWAB_TOKEN_PATH",
        os.path.expanduser("~/.config/schwab/token.json"),
    )

    # ── LLM ─────────────────────────────────────────────────────────────────
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    llm_api_key: str  = os.getenv("LLM_API_KEY", "")
    llm_model: str    = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    # ── Celery ──────────────────────────────────────────────────────────────
    celery_broker_url: str     = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")

    # ── Telegram Bot Settings ───────────────────────────────────────────────
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str   = os.getenv("TELEGRAM_CHAT_ID", "")

    # ── Alert Cooldown & Tuning Settings ──────────────────────────────────
    alert_min_pct_increase: float      = float(os.getenv("ALERT_MIN_PCT_INCREASE", "0.03"))
    alert_min_time_cooldown_mins: int  = int(os.getenv("ALERT_MIN_TIME_COOLDOWN_MINUTES", "2"))


settings = Settings()
