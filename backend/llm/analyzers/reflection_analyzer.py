"""
Reflection Analyzer.

Domain analyzer for post-market reflection generation and lesson extraction.
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from backend.llm.transport import LLMTransport
from backend.llm.prompts import build_reflection_prompt


class ReflectionAnalyzer:
    """Analyzes daily pick outcomes to generate reflections and lessons."""

    def __init__(self, transport: Optional[LLMTransport] = None):
        self.transport = transport or LLMTransport()

    def get_reflection(self, picks_data: List[dict]) -> Tuple[str, dict]:
        """
        Generates reflection text and extracts structured lessons dict.
        Returns (reflection_text, lessons_json).
        """
        if not picks_data:
            return "No picks data provided for reflection.", {}

        sys_p, user_p = build_reflection_prompt(picks_data)
        raw_res = self.transport.chat(user_p, system_prompt=sys_p, model_tier="fast", temperature=0.3)

        # Extract JSON block
        lessons = {}
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_res, re.DOTALL)
        if json_match:
            try:
                lessons = json.loads(json_match.group(1))
            except Exception:
                pass

        reflection_text = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", raw_res, flags=re.DOTALL).strip()
        return reflection_text, lessons
