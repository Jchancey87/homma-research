"""
Compare gpt-5-nano vs qwen3-32b vs gemini-2.5-flash-lite for our JSON extraction task.
"""
import sys, os, time, json
sys.path.insert(0, "/opt/trading-journal/backend")
from dotenv import load_dotenv
load_dotenv("/opt/trading-journal/backend/.env")
from openai import OpenAI
from config import Config

api_key = Config.LLM_API_KEY
base_url = Config.LLM_BASE_URL

SYSTEM = """You are a biotech equity research assistant. Extract the most significant upcoming catalyst.
Respond ONLY with valid JSON: {"upcoming_catalyst": "...", "catalyst_date": "YYYY-MM-DD or null"}"""

USER = """Ticker: SANA
Data: {"news_titles": ["Sana Biotechnology SC451 islet cell therapy diabetes trial enrollment complete", "SANA announces Phase 1 readout expected Q4 2026"], "sec_filings": []}"""

candidates = [
    "openai/gpt-5-nano",
    "qwen/qwen3-32b",
    "google/gemini-2.5-flash-lite",
]

for model in candidates:
    client = OpenAI(api_key=api_key, base_url=base_url, default_headers={
        "HTTP-Referer": "https://github.com/jchancey87/Analysis-App",
        "X-Title": "Trading Journal",
    })
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": USER},
            ],
            max_tokens=100,
            temperature=0.0,
        )
        elapsed = round(time.time() - t0, 2)
        content = resp.choices[0].message.content
        print(f"\n=== {model} ({elapsed}s) ===")
        print(f"Raw: {content!r}")
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        print(f"\n=== {model} ({elapsed}s) ERROR: {e}")
