"""Shared plumbing for feed-based sources (RSS and arXiv both speak
Atom/RSS XML). Kept private (leading underscore) — it's an implementation
detail of ``rss_source`` and ``arxiv_source``, not part of the public
ingestion API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import struct_time

import feedparser
import httpx

from persian_ai_pulse.retry import retry_with_backoff
from persian_ai_pulse.schemas import RawArticle, SourceType

logger = logging.getLogger(__name__)

_MAX_RAW_TEXT_CHARS = 8000


@retry_with_backoff(exceptions=(httpx.TransportError, httpx.HTTPStatusError), attempts=3)
def fetch_feed_bytes(url: str, *, timeout_s: float = 20.0, user_agent: str) -> bytes:
    """GET a feed URL with retry/backoff on transient network errors. Kept
    separate from parsing so tests can stub the network without touching
    ``feedparser``."""
    response = httpx.get(
        url,
        timeout=timeout_s,
        headers={"User-Agent": user_agent},
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.content


def _struct_time_to_dt(value: struct_time | None) -> datetime | None:
    if value is None:
        return None
    return datetime(*value[:6], tzinfo=timezone.utc)


def parsed_entry_to_raw_article(
    entry: feedparser.FeedParserDict,
    *,
    source_type: SourceType,
    source_name: str,
) -> RawArticle | None:
    """Best-effort conversion of one feed entry. Returns ``None`` (rather
    than raising) for entries missing the bare minimum (link/title), so one
    malformed item never aborts an otherwise-good feed."""
    url = entry.get("link")
    title = entry.get("title")
    if not url or not title:
        logger.warning("skipping feed entry with missing link/title: %r", entry.get("id"))
        return None

    published = (
        _struct_time_to_dt(entry.get("published_parsed"))
        or _struct_time_to_dt(entry.get("updated_parsed"))
        or datetime.now(timezone.utc)
    )

    body = entry.get("summary") or entry.get("description") or ""
    if not body and entry.get("content"):
        body = entry["content"][0].get("value", "")

    author = entry.get("author")

    try:
        return RawArticle(
            source_type=source_type,
            source_name=source_name,
            title=title.strip(),
            url=url,
            published_at=published,
            raw_text=body.strip()[:_MAX_RAW_TEXT_CHARS],
            author=author,
        )
    except Exception:
        logger.warning("skipping feed entry that failed validation: %s", url, exc_info=True)
        return None
