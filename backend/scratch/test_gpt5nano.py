"""
Direct API test to confirm gpt-5-nano model works with our OpenRouter key.
"""
import sys, os
sys.path.insert(0, "/opt/trading-journal/backend")
from dotenv import load_dotenv
load_dotenv("/opt/trading-journal/backend/.env")

from openai import OpenAI
from config import Config

print(f"Model: {Config.LLM_MODEL}")
print(f"Base URL: {Config.LLM_BASE_URL}")

client = OpenAI(
    api_key=Config.LLM_API_KEY,
    base_url=Config.LLM_BASE_URL,
    default_headers={
        "HTTP-Referer": "https://github.com/jchancey87/Analysis-App",
        "X-Title": "Trading Journal Analysis App",
    }
)

try:
    resp = client.chat.completions.create(
        model=Config.LLM_MODEL,
        messages=[
            {"role": "system", "content": "Respond ONLY with valid JSON: {\"status\": \"ok\", \"model\": \"your model name\"}"},
            {"role": "user", "content": "Test ping"},
        ],
        max_tokens=50,
        temperature=0.0,
    )
    print(f"Response: {resp.choices[0].message.content}")
    print(f"Model used: {resp.model}")
except Exception as e:
    print(f"ERROR: {e}")
