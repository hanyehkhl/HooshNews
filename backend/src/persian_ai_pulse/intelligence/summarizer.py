"""Turns a deduplicated ``RawArticle`` (or cluster representative) into a
``ProcessedArticle``: Persian title/summary/"why it matters", a category, an
importance score, and tags — via the configured ``LLMProvider``.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

from pydantic import BaseModel, Field

from persian_ai_pulse.intelligence.llm_provider import LLMProvider
from persian_ai_pulse.schemas import ProcessedArticle, RawArticle

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a meticulous Persian-language AI news editor writing for an Iranian \
developer/AI-practitioner audience. Given one article, respond with a single \
JSON object with exactly these keys:

- "title_fa": a concise, accurate Persian translation/rendering of the title.
- "summary_fa": a 2-3 sentence Persian summary of the article's actual content.
- "why_it_matters": 1-2 Persian sentences on why this specific audience should \
care (concrete impact, not generic hype).
- "category": a short English category label, e.g. "LLM / Release", \
"Research", "Tooling", "Policy", "Persian NLP".
- "importance_score": a float from 0 to 10 rating newsworthiness/impact for \
this audience.
- "tags": a JSON array of 2-5 short English tags.

Write only what the article supports. Do not fabricate numbers, dates, or \
quotes. Respond with JSON only, no prose, no markdown fences.
"""


class _SummaryPayload(BaseModel):
    title_fa: str
    summary_fa: str
    why_it_matters: str
    category: str
    importance_score: float = Field(ge=0, le=10)
    tags: list[str] = Field(default_factory=list)


def _build_user_prompt(article: RawArticle) -> str:
    return (
        f"Title: {article.title}\n"
        f"Source: {article.source_name}\n"
        f"Published: {article.published_at.isoformat()}\n"
        f"Body:\n{article.raw_text[:4000]}"
    )


def summarize_article(article: RawArticle, provider: LLMProvider) -> ProcessedArticle:
    raw = provider.complete_json(system=_SYSTEM_PROMPT, user=_build_user_prompt(article))
    payload = _SummaryPayload.model_validate(raw)
    return ProcessedArticle.from_raw(
        article,
        title_fa=payload.title_fa,
        summary_fa=payload.summary_fa,
        why_it_matters=payload.why_it_matters,
        category=payload.category,
        importance_score=payload.importance_score,
        tags=payload.tags,
    )


def summarize_articles(
    articles: Iterable[RawArticle],
    provider: LLMProvider,
    *,
    max_workers: int = 4,
) -> list[ProcessedArticle]:
    """Summarize concurrently (LLM calls are I/O-bound and independent per
    article) while isolating per-article failures — one bad LLM response
    (rate limit, malformed JSON) drops that article, not the whole run."""
    articles = list(articles)
    if not articles:
        return []

    results: list[ProcessedArticle] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(summarize_article, a, provider): a for a in articles}
        for future in as_completed(futures):
            article = futures[future]
            try:
                results.append(future.result())
            except Exception:
                logger.exception(
                    "failed to summarize article url=%s; dropping it from this digest",
                    article.url,
                )
    return results


def select_top_articles(articles: list[ProcessedArticle], *, limit: int) -> list[ProcessedArticle]:
    return sorted(articles, key=lambda a: a.importance_score, reverse=True)[:limit]
