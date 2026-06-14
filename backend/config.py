"""
backend/config.py — Single source of truth for all settings.

Historically this file (legacy `Config`, UPPER_CASE) and
``backend/fastapi_app/config.py`` (modern `Settings`, lowercase) both
read the same env vars but had **divergent defaults** — most critically,
``DATABASE_URL`` had a different password and host in each file. Whichever
module won the import race determined the runtime DB. RFC-003 unified them
into one file with two thin aliases (Config + Settings) that reference the
same underlying env-var reads.

Convention:
  - Services / jobs / scripts / Celery tasks keep using ``from config import Config`` (UPPER_CASE).
  - FastAPI app + async routers keep using ``from fastapi_app.config import settings`` (lowercase).
  - Both symbols resolve to the same env-var values; no more divergence.

Canonical default for ``DATABASE_URL`` is taken from the actively-running
FastAPI config (matches the production deploy target 192.168.0.201).
"""
import os
from dotenv import load_dotenv

load_dotenv()

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _normpath_relative_to(base: str, p: str) -> str:
    """Resolve relative paths against `base`; pass absolute paths through."""
    if os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(base, p))


# ── Raw env reads (the single point of access for every env var) ────────────

_raw_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql://journal:journal1@192.168.0.201:5432/trading_journal",
)
asyncpg_dsn = (
    _raw_db_url
    .replace("postgresql+asyncpg://", "postgresql://")
    .split("?")[0]   # strip ?sslmode=... — asyncpg uses ssl=False kwarg
)
_raw_storage = os.getenv("STORAGE_PATH", "../storage/charts")
storage_path = _normpath_relative_to(_BASE_DIR, _raw_storage)


# ── Modern lowercase API (preferred for new code) ───────────────────────────

class Settings:
    """Pydantic-style lowercase settings. Single source of truth."""

    # Database
    database_url: str = _raw_db_url
    asyncpg_dsn: str = asyncpg_dsn

    # Paths
    storage_path: str = storage_path

    # App meta
    app_title: str = "Homma Research API"
    app_version: str = "2.0.0"
    cors_origins: list = ["*"]  # tighten in production

    # Upload limits
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_mime_types: frozenset = frozenset({"image/png", "image/jpeg", "image/jpg", "image/webp"})
    allowed_extensions: frozenset = frozenset({"png", "jpg", "jpeg", "webp"})

    # External APIs
    polygon_api_key: str = os.getenv("POLYGON_API_KEY", "")
    fmp_api_key: str = os.getenv("FMP_API_KEY", "")
    sec_user_agent: str = os.getenv("SEC_USER_AGENT", "TradingJournal trader@example.com")

    # Schwab
    schwab_api_key: str = os.getenv("SCHWAB_API_KEY", "")
    schwab_api_secret: str = os.getenv("SCHWAB_API_SECRET", "")
    schwab_callback_url: str = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182")
    schwab_token_path: str = os.getenv(
        "SCHWAB_TOKEN_PATH", os.path.expanduser("~/.config/schwab/token.json")
    )

    # LLM (Groq / fast tasks)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    # LLM (OpenRouter / deep research)
    deep_llm_base_url: str = os.getenv("DEEP_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    deep_llm_api_key: str = os.getenv("DEEP_LLM_API_KEY", os.getenv("DEEP_LLM_KEY", ""))
    deep_llm_model: str = os.getenv("DEEP_LLM_MODEL", "meta-llama/llama-3.3-70b-instruct")

    # Vision (Gemini / OpenAI-compatible)
    vision_base_url: str = os.getenv("VISION_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    vision_api_key: str = os.getenv("VISION_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    vision_model: str = os.getenv("VISION_MODEL", "gemini-1.5-pro")

    # Celery
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")

    # SMTP / notifications
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    notify_email: str = os.getenv("NOTIFY_EMAIL", "")

    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Alert tuning
    alert_min_pct_increase: float = float(os.getenv("ALERT_MIN_PCT_INCREASE", "0.03"))
    alert_min_time_cooldown_mins: int = int(os.getenv("ALERT_MIN_TIME_COOLDOWN_MINUTES", "2"))


settings = Settings()


# ── Legacy UPPER_CASE API (kept for backward compatibility) ──────────────────

class Config:
    """Legacy UPPER_CASE accessor. Aliases the unified Settings values.
    Used by 18 services / jobs / scripts that pre-date the FastAPI refactor.
    New code should prefer the lowercase ``settings`` instance.
    """

    BASE_DIR = _BASE_DIR

    # Database
    DATABASE_URL = settings.database_url

    # Paths
    STORAGE_PATH = settings.storage_path

    # LLM (Groq / OpenRouter / Vision)
    LLM_BASE_URL = settings.llm_base_url
    LLM_API_KEY = settings.llm_api_key
    LLM_MODEL = settings.llm_model
    DEEP_LLM_BASE_URL = settings.deep_llm_base_url
    DEEP_LLM_API_KEY = settings.deep_llm_api_key
    DEEP_LLM_MODEL = settings.deep_llm_model
    VISION_BASE_URL = settings.vision_base_url
    VISION_API_KEY = settings.vision_api_key
    VISION_MODEL = settings.vision_model

    # External APIs
    POLYGON_API_KEY = settings.polygon_api_key
    FMP_API_KEY = settings.fmp_api_key
    SEC_USER_AGENT = settings.sec_user_agent

    # Schwab
    SCHWAB_API_KEY = settings.schwab_api_key
    SCHWAB_API_SECRET = settings.schwab_api_secret
    SCHWAB_CALLBACK_URL = settings.schwab_callback_url
    SCHWAB_TOKEN_PATH = settings.schwab_token_path

    # Upload limits
    MAX_UPLOAD_BYTES = settings.max_upload_bytes
    ALLOWED_MIME_TYPES = settings.allowed_mime_types
    ALLOWED_EXTENSIONS = settings.allowed_extensions

    # SMTP / notifications
    SMTP_SERVER = settings.smtp_server
    SMTP_PORT = settings.smtp_port
    SMTP_USER = settings.smtp_user
    SMTP_PASSWORD = settings.smtp_password
    NOTIFY_EMAIL = settings.notify_email

    # Telegram
    TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
    TELEGRAM_CHAT_ID = settings.telegram_chat_id

    # Alert tuning
    ALERT_MIN_PCT_INCREASE = settings.alert_min_pct_increase
    ALERT_MIN_TIME_COOLDOWN_MINS = settings.alert_min_time_cooldown_mins
