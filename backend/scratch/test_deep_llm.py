import sys
import os

# Ensure backend/ is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.llm_client import _chat, DEEP_RESEARCH_SYSTEM
from config import Config

def test_deep_llm_call():
    print(f"\nDEEP LLM MODEL: {Config.DEEP_LLM_MODEL}")
    print(f"DEEP LLM BASE URL: {Config.DEEP_LLM_BASE_URL}")
    print(f"DEEP LLM KEY EXISTS: {bool(Config.DEEP_LLM_API_KEY)}")
    
    try:
        response = _chat(
            system="You are a helpful assistant.",
            user="Say hello in 5 words or less.",
            max_tokens=20,
            use_deep_client=True
        )
        print(f"RESPONSE:\n{response}")
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
    assert True
