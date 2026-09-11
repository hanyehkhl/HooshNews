"""Generic RSS/Atom source — covers lab blogs and Iranian AI newsletters
alike. One instance per feed URL; the pipeline holds a list of these built
from a plain config list (see ``pipeline.build_default_sources``)."""

from __future__ import annotations

import feedparser

from persian_ai_pulse.ingest._feed_utils import fetch_feed_bytes, parsed_entry_to_raw_article
from persian_ai_pulse.ingest.base import SourceFetcher
from persian_ai_pulse.schemas import RawArticle, SourceType

_USER_AGENT = "PersianAIPulse/0.1 (+https://github.com/hanyehkhl/HooshNews)"


class RssSource(SourceFetcher):
    def __init__(self, name: str, feed_url: str, *, timeout_s: float = 20.0) -> None:
        self.name = name
        self.feed_url = feed_url
        self.timeout_s = timeout_s

    def fetch(self) -> list[RawArticle]:
        raw_bytes = fetch_feed_bytes(self.feed_url, timeout_s=self.timeout_s, user_agent=_USER_AGENT)
        parsed = feedparser.parse(raw_bytes)

        if parsed.bozo and not parsed.entries:
            raise ValueError(f"feed at {self.feed_url!r} did not parse: {parsed.bozo_exception}")

        articles: list[RawArticle] = []
        for entry in parsed.entries:
            article = parsed_entry_to_raw_article(
                entry, source_type=SourceType.RSS, source_name=self.name
            )
            if article is not None:
                articles.append(article)
        return articles

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"RssSource(name={self.name!r}, feed_url={self.feed_url!r})"
