"""Orchestrates the configured ``SourceFetcher`` instances into one flat,
deduplicated-by-source-volume list of ``RawArticle``.

Two responsibilities live here that don't belong in any single source:

1. **Concurrency** — sources are I/O-bound and independent, so they're
   fetched in a thread pool rather than serially.
2. **The coverage gate** — without it, one high-volume feed (e.g. a lab that
   posts 40 blog entries a day) can crowd out every other source before the
   intelligence layer even sees the rest. This mirrors the "coverage gate"
   called out in the original architecture sketch (inspired by AiNews'
   per-source fairness handling).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from persian_ai_pulse.config import Settings
from persian_ai_pulse.ingest.arxiv_source import ArxivSource
from persian_ai_pulse.ingest.base import SourceFetcher
from persian_ai_pulse.ingest.rss_source import RssSource
from persian_ai_pulse.ingest.telegram_source import TelegramChannelSource
from persian_ai_pulse.schemas import RawArticle

logger = logging.getLogger(__name__)


def run_ingestion(sources: list[SourceFetcher], *, max_workers: int = 8) -> list[RawArticle]:
    """Fetch every source concurrently. Each source is isolated via
    ``safe_fetch`` — one dead feed reduces coverage, it never aborts the run."""
    if not sources:
        return []
    articles: list[RawArticle] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(sources))) as pool:
        for result in pool.map(lambda s: s.safe_fetch(), sources):
            articles.extend(result)
    logger.info("ingestion complete: %d sources, %d raw articles", len(sources), len(articles))
    return articles


def apply_coverage_gate(articles: list[RawArticle], *, max_per_source: int) -> list[RawArticle]:
    """Keep at most ``max_per_source`` articles (the newest ones) from any
    single ``source_name``, so downstream ranking sees a balanced slate."""
    counts: dict[str, int] = defaultdict(int)
    gated: list[RawArticle] = []
    for article in sorted(articles, key=lambda a: a.published_at, reverse=True):
        if counts[article.source_name] >= max_per_source:
            continue
        counts[article.source_name] += 1
        gated.append(article)
    return gated


def build_sources_from_config(
    config_path: Path, settings: Settings
) -> list[SourceFetcher]:
    """Build the source list from a plain JSON config instead of hardcoding
    feed URLs — adding/removing a feed is then a one-line config edit, not a
    code change. See ``backend/config/sources.example.json`` for the shape."""
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    sources: list[SourceFetcher] = []

    for feed in raw.get("rss_feeds", []):
        sources.append(RssSource(name=feed["name"], feed_url=feed["url"]))

    arxiv_cfg = raw.get("arxiv")
    if arxiv_cfg:
        sources.append(
            ArxivSource(
                categories=arxiv_cfg.get("categories"),
                search_query=arxiv_cfg.get("search_query"),
                max_results=arxiv_cfg.get("max_results", 25),
            )
        )

    if raw.get("telegram_channels") and settings.telegram_ingest.is_configured:
        sources.append(
            TelegramChannelSource(
                api_id=settings.telegram_ingest.api_id,  # type: ignore[arg-type]
                api_hash=settings.telegram_ingest.api_hash,
                session_string=settings.telegram_ingest.session_string,
                channels=raw["telegram_channels"],
            )
        )
    elif raw.get("telegram_channels"):
        logger.warning(
            "telegram_channels configured but PAP_TG_INGEST_* credentials are missing; "
            "skipping Telegram ingestion for this run"
        )

    return sources
