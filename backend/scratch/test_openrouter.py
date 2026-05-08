import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# 1. Load env
load_dotenv()

# 2. Get credentials
base_url = os.getenv('DEEP_LLM_BASE_URL', 'https://openrouter.ai/api/v1')
api_key  = os.getenv('DEEP_LLM_API_KEY', '')
model    = os.getenv('DEEP_LLM_MODEL', 'meta-llama/llama-3.3-70b-instruct')

print(f"--- Dry Run Test ---")
print(f"URL:   {base_url}")
print(f"Model: {model}")
print(f"Key:   {'[SET]' if api_key else '[MISSING]'} (first 5 chars: {api_key[:5] if api_key else 'N/A'})")

if not api_key:
    print("\nERROR: DEEP_LLM_API_KEY is missing from .env!")
    sys.exit(1)

# 3. Test Call
client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    default_headers={
        "HTTP-Referer": "https://github.com/jchancey87/Analysis-App",
        "X-Title": "Dry Run Test",
    }
)

try:
    print("\nSending test message...")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say 'OpenRouter is active'"}],
        max_tokens=20
    )
    print(f"Response: {response.choices[0].message.content.strip()}")
    print("\nSUCCESS: Connection works.")
except Exception as e:
    print(f"\nFAILURE: {e}")
