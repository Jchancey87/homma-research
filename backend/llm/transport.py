"""
LLM Transport Layer.

Deep module handling client initialization, model routing (fast vs deep),
HTTP headers, retry/fallback, and API execution. Supports dependency injection.
"""

from typing import Optional
from openai import OpenAI
from config import Config


class LLMTransport:
    """
    Handles transport calls to OpenAI-compatible LLM providers (Groq, OpenRouter, etc.).
    Supports injected clients for zero-network testing.
    """

    def __init__(
        self,
        client: Optional[OpenAI] = None,
        deep_client: Optional[OpenAI] = None
    ):
        self._client = client
        self._deep_client = deep_client

    def get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=Config.LLM_API_KEY,
                base_url=Config.LLM_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://github.com/jchancey87/Analysis-App",
                    "X-Title": "Trading Journal Analysis App",
                }
            )
        return self._client

    def get_deep_client(self) -> OpenAI:
        if self._deep_client is None:
            api_key = Config.DEEP_LLM_API_KEY or Config.LLM_API_KEY
            base_url = Config.DEEP_LLM_BASE_URL if Config.DEEP_LLM_API_KEY else Config.LLM_BASE_URL
            self._deep_client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers={
                    "HTTP-Referer": "https://github.com/jchancey87/Analysis-App",
                    "X-Title": "Trading Journal Analysis App",
                }
            )
        return self._deep_client

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        model_tier: str = "fast",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Execute chat completion against target model tier ('fast' or 'deep').
        Returns response text string.
        """
        client = self.get_deep_client() if model_tier == "deep" else self.get_client()
        model_name = (
            Config.DEEP_LLM_MODEL
            if (model_tier == "deep" and Config.DEEP_LLM_API_KEY)
            else Config.LLM_MODEL
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
