from datetime import datetime, timezone

from persian_ai_pulse.intelligence.summarizer import (
    select_top_articles,
    summarize_article,
    summarize_articles,
)
from persian_ai_pulse.schemas import ProcessedArticle, RawArticle, SourceType


def _raw_article(idx: int) -> RawArticle:
    return RawArticle(
        source_type=SourceType.RSS,
        source_name="Test Source",
        title=f"Title {idx}",
        url=f"https://example.com/{idx}",
        published_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
        raw_text=f"Body {idx}",
    )


class FakeLLMProvider:
    """Implements the ``LLMProvider`` protocol with a canned response, so
    ``summarizer`` can be tested without any real API calls."""

    def __init__(self, response: dict | None = None, *, raise_for: set[str] | None = None):
        self._response = response or {
            "title_fa": "عنوان تستی",
            "summary_fa": "خلاصه تستی.",
            "why_it_matters": "چون تستی است.",
            "category": "Research",
            "importance_score": 6.5,
            "tags": ["test"],
        }
        self._raise_for = raise_for or set()

    def complete_json(self, *, system: str, user: str) -> dict:
        if any(marker in user for marker in self._raise_for):
            raise RuntimeError("simulated provider failure")
        return self._response


def test_summarize_article_maps_llm_response_onto_processed_article():
    article = summarize_article(_raw_article(1), FakeLLMProvider())
    assert isinstance(article, ProcessedArticle)
    assert article.title_fa == "عنوان تستی"
    assert article.importance_score == 6.5


def test_summarize_articles_skips_failures_without_aborting_the_batch():
    raw = [_raw_article(1), _raw_article(2), _raw_article(3)]
    provider = FakeLLMProvider(raise_for={"Title 2"})

    results = summarize_articles(raw, provider, max_workers=2)

    assert len(results) == 2
    assert {a.title_en for a in results} == {"Title 1", "Title 3"}


def test_summarize_articles_handles_empty_input():
    assert summarize_articles([], FakeLLMProvider()) == []


def test_select_top_articles_orders_by_score_desc_and_respects_limit():
    processed = [
        summarize_article(
            _raw_article(i),
            FakeLLMProvider({**FakeLLMProvider()._response, "importance_score": score}),
        )
        for i, score in enumerate([3.0, 9.0, 5.0])
    ]
    top = select_top_articles(processed, limit=2)
    assert [a.importance_score for a in top] == [9.0, 5.0]
