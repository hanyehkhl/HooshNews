"""The contract every data source must satisfy.

Deliberately minimal: one method, one return type. This is the seam that
makes the ingestion layer modular — ``pipeline.py`` never knows or cares
whether a ``SourceFetcher`` talks to RSS, arXiv, or Telegram.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from persian_ai_pulse.schemas import RawArticle

logger = logging.getLogger(__name__)


class SourceFetcher(ABC):
    """A single data source (one RSS feed, one arXiv query, one Telegram
    channel list, ...). Implementations must be defensive: a single failing
    source (feed down, rate-limited, malformed XML) must never take down the
    whole ingestion run."""

    #: Human-readable name surfaced in ``RawArticle.source_name`` and in logs.
    name: str = "unnamed-source"

    @abstractmethod
    def fetch(self) -> list[RawArticle]:
        """Return newly-seen articles. Implementations should raise only for
        truly unexpected errors; recoverable per-item issues (one malformed
        entry in an otherwise fine feed) should be logged and skipped."""
        raise NotImplementedError

    def safe_fetch(self) -> list[RawArticle]:
        """Wrapper used by the pipeline: isolates one source's failure from
        the rest of the run instead of letting one dead feed abort the day's
        digest."""
        try:
            articles = self.fetch()
            logger.info("source=%s fetched=%d", self.name, len(articles))
            return articles
        except Exception:
            logger.exception("source=%s failed; skipping this source for this run", self.name)
            return []
