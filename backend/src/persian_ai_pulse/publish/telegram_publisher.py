"""Publishes the daily digest via the Telegram **Bot** API.

Deliberately independent of ``ingest.telegram_source.TelegramChannelSource``:
that module needs a full user session to read channel history; this one
needs only a bot token, and a bot can never read another channel's history.
Keeping them separate means a bot-token rotation can never break ingestion,
and a stale scraping session can never break publishing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from persian_ai_pulse.config import TelegramPublishSettings
from persian_ai_pulse.retry import retry_with_backoff
from persian_ai_pulse.schemas import DailyDigest

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"
_RETRYABLE = (httpx.TransportError,)


class TelegramPublisher:
    def __init__(self, settings: TelegramPublishSettings, *, timeout_s: float = 30.0) -> None:
        if not settings.is_configured:
            raise ValueError("Telegram publish settings are not configured (bot_token/chat_id)")
        self._settings = settings
        self._timeout_s = timeout_s

    def _url(self, method: str) -> str:
        return f"{_API_BASE}/bot{self._settings.bot_token}/{method}"

    @retry_with_backoff(exceptions=_RETRYABLE, attempts=3)
    def send_text_digest(self, digest: DailyDigest, *, top_n: int = 5) -> None:
        lines = [f"\U0001F4F0 <b>خلاصه اخبار هوش مصنوعی — {digest.date}</b>"]
        for article in digest.articles[:top_n]:
            lines.append(
                f"• <b>{article.title_fa}</b>\n{article.why_it_matters}\n{article.original_url}"
            )
        text = "\n\n".join(lines)

        response = httpx.post(
            self._url("sendMessage"),
            json={"chat_id": self._settings.chat_id, "text": text, "parse_mode": "HTML"},
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        logger.info("telegram: published text digest for %s", digest.date)

    @retry_with_backoff(exceptions=_RETRYABLE, attempts=3)
    def send_audio_digest(self, digest: DailyDigest, audio_path: Path) -> None:
        with audio_path.open("rb") as audio_file:
            response = httpx.post(
                self._url("sendAudio"),
                data={"chat_id": self._settings.chat_id, "caption": f"\U0001F3A7 پادکست خبری {digest.date}"},
                files={"audio": (audio_path.name, audio_file, "audio/mpeg")},
                timeout=self._timeout_s,
            )
        response.raise_for_status()
        logger.info("telegram: published audio digest for %s", digest.date)


def notify_failure(bot_token: str, chat_id: str, message: str) -> None:
    """Best-effort admin alert used by the CI failure step. Never raises —
    a broken alert path must not mask the original pipeline failure, and
    must not fail the CI job a second time."""
    try:
        httpx.post(
            f"{_API_BASE}/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"⚠️ Persian AI Pulse pipeline failed:\n{message[:3500]}",
            },
            timeout=10.0,
        )
    except Exception:
        logger.exception("failed to send failure notification to the telegram admin chat")
