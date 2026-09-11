"""Text-to-speech provider abstraction.

Default is ``edge`` (Microsoft Edge's free neural TTS via the ``edge-tts``
library), which ships solid Persian voices at zero API cost — the right
default for a "zero-server, zero-cost" pipeline. ``openai`` is available as a
drop-in swap if edge-tts voices are ever degraded/blocked, at the cost of a
paid API call per digest.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Protocol

from persian_ai_pulse.config import TTSSettings

logger = logging.getLogger(__name__)


class TTSProvider(Protocol):
    def synthesize(self, text: str, out_path: Path) -> None: ...


class EdgeTTSProvider:
    """Free Microsoft Edge neural TTS. ``edge-tts`` is optional
    (``pip install persian-ai-pulse[tts]``) and imported lazily."""

    def __init__(self, voice: str) -> None:
        self.voice = voice

    def synthesize(self, text: str, out_path: Path) -> None:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed; install with `pip install 'persian-ai-pulse[tts]'`"
            ) from exc

        out_path.parent.mkdir(parents=True, exist_ok=True)

        async def _run() -> None:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(out_path))

        asyncio.run(_run())
        logger.info("edge-tts: wrote %s (%d chars)", out_path, len(text))


class OpenAITTSProvider:
    """Paid fallback using any OpenAI-compatible ``audio.speech`` endpoint."""

    def __init__(self, settings: TTSSettings) -> None:
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
                api_key=self._settings.openai_api_key,
                base_url=self._settings.openai_base_url,
            )
        return self._client

    def synthesize(self, text: str, out_path: Path) -> None:
        client = self._client_or_create()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with client.audio.speech.with_streaming_response.create(
            model=self._settings.openai_model,
            voice="alloy",
            input=text,
        ) as response:
            response.stream_to_file(str(out_path))
        logger.info("openai-tts: wrote %s (%d chars)", out_path, len(text))


def build_default_provider(settings: TTSSettings) -> TTSProvider:
    if settings.provider == "openai":
        return OpenAITTSProvider(settings)
    return EdgeTTSProvider(settings.voice)
