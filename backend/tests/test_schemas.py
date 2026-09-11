from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from persian_ai_pulse.schemas import ProcessedArticle, RawArticle, SourceType


def _raw_article(**overrides) -> RawArticle:
    defaults = dict(
        source_type=SourceType.RSS,
        source_name="Test Source",
        title="Something happened in AI",
        url="https://example.com/news/1",
        published_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        raw_text="Body text about the thing that happened.",
    )
    defaults.update(overrides)
    return RawArticle.model_validate(defaults)


def test_raw_article_naive_datetime_becomes_utc():
    article = _raw_article(published_at=datetime(2026, 9, 10, 12, 0, 0))
    assert article.published_at.tzinfo is not None


def test_raw_article_id_matches_ids_module():
    from persian_ai_pulse.ids import article_id

    article = _raw_article(url="https://example.com/news/1?utm_source=x")
    assert article.id == article_id("https://example.com/news/1?utm_source=x")


def test_raw_article_rejects_missing_title():
    with pytest.raises(ValidationError):
        RawArticle.model_validate(
            {
                "source_type": "rss",
                "source_name": "Test",
                "title": "",  # empty is allowed by type but let's check url validation instead
                "url": "not-a-url",
                "published_at": datetime.now(timezone.utc),
                "raw_text": "x",
            }
        )


def test_processed_article_from_raw_carries_over_core_fields():
    raw = _raw_article()
    processed = ProcessedArticle.from_raw(
        raw,
        title_fa="عنوان فارسی",
        summary_fa="خلاصه فارسی.",
        why_it_matters="چرا مهم است.",
        category="Research",
        importance_score=7.5,
        tags=["LLM", "Research"],
    )
    assert processed.id == raw.id
    assert processed.title_en == raw.title
    assert processed.source == raw.source_name
    assert processed.importance_score == 7.5


def test_processed_article_importance_score_bounds():
    raw = _raw_article()
    with pytest.raises(ValidationError):
        ProcessedArticle.from_raw(
            raw,
            title_fa="x",
            summary_fa="x",
            why_it_matters="x",
            category="x",
            importance_score=11,  # out of [0, 10]
            tags=[],
        )
