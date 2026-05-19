import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Paths
    BASE_DIR        = os.path.dirname(os.path.abspath(__file__))

    # ── Database (PostgreSQL) ───────────────────────────────────────────────
    # Full DSN — used by psycopg2.connect()
    DATABASE_URL    = os.getenv(
        'DATABASE_URL',
        'postgresql://journal:journal@localhost:5432/trading_journal'
    )

    _env_storage    = os.getenv('STORAGE_PATH', '../storage/charts')
    STORAGE_PATH    = os.path.normpath(os.path.join(BASE_DIR, _env_storage)) if not os.path.isabs(_env_storage) else _env_storage

    # Primary LLM (Groq / Fast Tasks)
    LLM_BASE_URL    = os.getenv('LLM_BASE_URL', 'https://api.groq.com/openai/v1')
    LLM_API_KEY     = os.getenv('LLM_API_KEY', '')
    LLM_MODEL       = os.getenv('LLM_MODEL', 'llama-3.3-70b-versatile')

    # Secondary LLM (OpenRouter / Deep Research)
    DEEP_LLM_BASE_URL = os.getenv('DEEP_LLM_BASE_URL', 'https://openrouter.ai/api/v1')
    DEEP_LLM_API_KEY  = os.getenv('DEEP_LLM_API_KEY', '')
    DEEP_LLM_MODEL    = os.getenv('DEEP_LLM_MODEL', 'meta-llama/llama-3.3-70b-instruct')

    # External APIs
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    FMP_API_KEY     = os.getenv('FMP_API_KEY', '')        # Financial Modeling Prep
    SEC_USER_AGENT  = os.getenv('SEC_USER_AGENT', 'TradingJournal trader@example.com')

    # Schwab API
    SCHWAB_API_KEY      = os.getenv('SCHWAB_API_KEY', '')
    SCHWAB_API_SECRET   = os.getenv('SCHWAB_API_SECRET', '')
    SCHWAB_CALLBACK_URL = os.getenv('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')
    SCHWAB_TOKEN_PATH   = os.getenv('SCHWAB_TOKEN_PATH', os.path.expanduser('~/.config/schwab/token.json'))

    # Vision API (OpenAI-compatible)
    VISION_BASE_URL = os.getenv('VISION_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/')
    VISION_API_KEY  = os.getenv('VISION_API_KEY', os.getenv('GEMINI_API_KEY', ''))
    VISION_MODEL    = os.getenv('VISION_MODEL', 'gemini-1.5-pro')

    # Upload limits
    MAX_UPLOAD_BYTES    = 10 * 1024 * 1024   # 10 MB
    ALLOWED_MIME_TYPES  = {'image/png', 'image/jpeg', 'image/jpg', 'image/webp'}
    ALLOWED_EXTENSIONS  = {'png', 'jpg', 'jpeg', 'webp'}

    # SMTP / Notifications
    SMTP_SERVER         = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT           = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER           = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD       = os.getenv('SMTP_PASSWORD', '')
    NOTIFY_EMAIL        = os.getenv('NOTIFY_EMAIL', '')
