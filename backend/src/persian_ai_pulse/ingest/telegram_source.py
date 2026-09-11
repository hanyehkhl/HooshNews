"""Telegram channel source, built on a *user* session (Telethon).

Telegram's Bot API cannot read another channel's message history — only a
logged-in user account can — so ingestion necessarily needs different
credentials than publishing. This module is kept deliberately independent
from ``persian_ai_pulse.publish.telegram_publisher`` (which only needs a bot
token): rotating the bot token can never break scraping, and a scraping
session going stale can never break publishing.

``telethon`` is an optional dependency (``pip install persian-ai-pulse[telegram]``)
and is imported lazily so the rest of the package works without it installed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from persian_ai_pulse.ingest.base import SourceFetcher
from persian_ai_pulse.schemas import RawArticle, SourceType

logger = logging.getLogger(__name__)

_MAX_RAW_TEXT_CHARS = 8000


class TelegramChannelSource(SourceFetcher):
    name = "telegram"

    def __init__(
        self,
        *,
        api_id: int,
        api_hash: str,
        session_string: str,
        channels: list[str],
        lookback_hours: int = 24,
        limit_per_channel: int = 50,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_string = session_string
        self.channels = channels
        self.lookback_hours = lookback_hours
        self.limit_per_channel = limit_per_channel

    def fetch(self) -> list[RawArticle]:
        client_cls, session_cls = self._import_telethon()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        articles: list[RawArticle] = []

        with client_cls(session_cls(self.session_string), self.api_id, self.api_hash) as client:
            for channel in self.channels:
                try:
                    articles.extend(self._fetch_channel(client, channel, cutoff))
                except Exception:
                    logger.exception(
                        "failed to fetch telegram channel=%s; skipping it", channel
                    )
        return articles

    @staticmethod
    def _import_telethon() -> tuple[Any, Any]:
        try:
            from telethon.sessions import StringSession
            from telethon.sync import TelegramClient
        except ImportError as exc:  # pragma: no cover - exercised only without extra installed
            raise RuntimeError(
                "telethon is not installed; install with "
                "`pip install 'persian-ai-pulse[telegram]'`"
            ) from exc
        return TelegramClient, StringSession

    def _fetch_channel(self, client: Any, channel: str, cutoff: datetime) -> list[RawArticle]:
        out: list[RawArticle] = []
        for message in client.iter_messages(channel, limit=self.limit_per_channel):
            if message.date < cutoff:
                break
            text = (message.raw_text or "").strip()
            if not text:
                continue

            handle = channel.lstrip("@")
            url = f"https://t.me/{handle}/{message.id}"
            title = text.splitlines()[0][:200]

            try:
                out.append(
                    RawArticle(
                        source_type=SourceType.TELEGRAM,
                        source_name=f"t.me/{handle}",
                        title=title,
                        url=url,
                        published_at=message.date,
                        raw_text=text[:_MAX_RAW_TEXT_CHARS],
                        author=channel,
                    )
                )
            except Exception:
                logger.warning("skipping malformed telegram message url=%s", url, exc_info=True)
        return out

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"TelegramChannelSource(channels={self.channels!r})"
