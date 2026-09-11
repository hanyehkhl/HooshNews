"""Pydantic schemas shared across every layer of the pipeline.

Keeping these in one module (rather than letting each layer define its own
ad-hoc dicts) is what makes ``ingest`` → ``intelligence`` → ``publish``
composable: each layer's public functions take and return these types, so
any layer can be swapped, tested, or run standalone.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, field_validator

from persian_ai_pulse.ids import article_id


class SourceType(StrEnum):
    RSS = "rss"
    ARXIV = "arxiv"
    TELEGRAM = "telegram"


class RawArticle(BaseModel):
    """Normalized output of the ingestion layer — the single schema every
    ``SourceFetcher`` must produce, regardless of where the data came from."""

    source_type: SourceType
    source_name: str
    title: str
    url: HttpUrl
    published_at: datetime
    raw_text: str = Field(description="Best-effort plain-text body/summary as fetched.")
    author: str | None = None

    @field_validator("published_at")
    @classmethod
    def _ensure_tz_aware(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)

    @property
    def id(self) -> str:
        return article_id(str(self.url))


class ProcessedArticle(BaseModel):
    """Output of the intelligence layer: a ``RawArticle`` enriched with a
    Persian summary, ranking, and tags. This is the shape written to the
    JSON store and consumed by the frontend."""

    id: str
    title_fa: str
    title_en: str
    source: str
    category: str
    importance_score: float = Field(ge=0, le=10)
    summary_fa: str
    why_it_matters: str
    original_url: HttpUrl
    tags: list[str] = Field(default_factory=list)
    published_at: datetime

    @classmethod
    def from_raw(
        cls,
        raw: RawArticle,
        *,
        title_fa: str,
        summary_fa: str,
        why_it_matters: str,
        category: str,
        importance_score: float,
        tags: list[str],
    ) -> "ProcessedArticle":
        return cls(
            id=raw.id,
            title_fa=title_fa,
            title_en=raw.title,
            source=raw.source_name,
            category=category,
            importance_score=importance_score,
            summary_fa=summary_fa,
            why_it_matters=why_it_matters,
            original_url=raw.url,
            tags=tags,
            published_at=raw.published_at,
        )


class DailyDigest(BaseModel):
    """One day's worth of published output — the JSON payload the frontend
    fetches for a given date, and the unit the JSON store persists."""

    date: str = Field(description="ISO date, e.g. 2026-09-11")
    generated_at: datetime
    daily_audio_url: str | None = None
    articles: list[ProcessedArticle] = Field(default_factory=list)


class DigestIndexEntry(BaseModel):
    date: str
    article_count: int
    has_audio: bool


class DigestIndex(BaseModel):
    """Small, cheap-to-fetch manifest of available days. The frontend loads
    this first, then fetches only the day(s) it actually needs — this is
    what keeps a single ever-growing ``releases.json`` from becoming the
    site's load-time bottleneck."""

    updated_at: datetime
    days: list[DigestIndexEntry] = Field(default_factory=list)
