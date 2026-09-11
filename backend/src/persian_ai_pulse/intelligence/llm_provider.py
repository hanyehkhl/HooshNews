"""LLM provider abstraction.

Any OpenAI-Chat-Completions-compatible endpoint satisfies ``LLMProvider`` —
OpenAI, Groq, Together.ai, OpenRouter, or a self-hosted vLLM/Ollama server.
Swapping providers is a config change (``PAP_LLM_BASE_URL`` / ``PAP_LLM_MODEL``
/ ``PAP_LLM_API_KEY``), never a code change.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from persian_ai_pulse.config import LLMSettings
from persian_ai_pulse.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """A chat model that can be asked to return a JSON object."""

    def complete_json(self, *, system: str, user: str) -> dict: ...


class LLMResponseError(RuntimeError):
    """Raised when the provider's response isn't valid JSON."""


class OpenAICompatibleProvider:
    """Default, production ``LLMProvider``. The ``openai`` SDK is imported
    lazily so modules that only need dedup or TTS don't require it."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._client = None

    def _client_or_create(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai is not installed; install with "
                    "`pip install 'persian-ai-pulse[intelligence]'`"
                ) from exc
            self._client = OpenAI(
                api_key=self._settings.api_key or "unused-for-local-endpoints",
                base_url=self._settings.base_url,
                timeout=self._settings.request_timeout_s,
            )
        return self._client

    @retry_with_backoff(exceptions=(TimeoutError, ConnectionError), attempts=3, max_delay_s=8)
    def complete_json(self, *, system: str, user: str) -> dict:
        client = self._client_or_create()
        response = client.chat.completions.create(
            model=self._settings.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"provider returned non-JSON content: {content[:200]!r}") from exc


def build_default_provider(settings: LLMSettings) -> LLMProvider:
    return OpenAICompatibleProvider(settings)
