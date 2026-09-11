"""arXiv source, built on the same Atom-feed machinery as ``RssSource``.

arXiv's export API (``export.arxiv.org/api/query``) returns Atom XML, so it
needs no bespoke HTTP client — only a query-string builder and a distinct
``SourceType`` tag.
"""

from __future__ import annotations

from urllib.parse import quote

import feedparser

from persian_ai_pulse.ingest._feed_utils import fetch_feed_bytes, parsed_entry_to_raw_article
from persian_ai_pulse.ingest.base import SourceFetcher
from persian_ai_pulse.schemas import RawArticle, SourceType

_USER_AGENT = "PersianAIPulse/0.1 (+https://github.com/hanyehkhl/HooshNews)"
_API_URL = "https://export.arxiv.org/api/query"


class ArxivSource(SourceFetcher):
    """Fetches the newest papers matching ``categories`` (e.g. ``cs.CL``,
    ``cs.AI``) and/or a free-text ``search_query``."""

    def __init__(
        self,
        *,
        categories: list[str] | None = None,
        search_query: str | None = None,
        max_results: int = 25,
        timeout_s: float = 20.0,
    ) -> None:
        if not categories and not search_query:
            raise ValueError("ArxivSource requires at least one of categories/search_query")
        self.name = "arxiv"
        self.categories = categories or []
        self.search_query = search_query
        self.max_results = max_results
        self.timeout_s = timeout_s

    def _build_url(self) -> str:
        clauses = [f"cat:{cat}" for cat in self.categories]
        if self.search_query:
            clauses.append(f"all:{self.search_query}")
        query = quote(" OR ".join(clauses))
        return (
            f"{_API_URL}?search_query={query}"
            f"&sortBy=submittedDate&sortOrder=descending&max_results={self.max_results}"
        )

    def fetch(self) -> list[RawArticle]:
        raw_bytes = fetch_feed_bytes(self._build_url(), timeout_s=self.timeout_s, user_agent=_USER_AGENT)
        parsed = feedparser.parse(raw_bytes)

        articles: list[RawArticle] = []
        for entry in parsed.entries:
            article = parsed_entry_to_raw_article(
                entry, source_type=SourceType.ARXIV, source_name=self.name
            )
            if article is not None:
                articles.append(article)
        return articles

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ArxivSource(categories={self.categories!r})"
