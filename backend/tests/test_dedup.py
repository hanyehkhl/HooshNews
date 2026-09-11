from datetime import datetime, timedelta, timezone

import numpy as np

from persian_ai_pulse.intelligence.dedup import deduplicate
from persian_ai_pulse.schemas import RawArticle, SourceType

_NOW = datetime(2026, 9, 11, 6, 0, tzinfo=timezone.utc)


def _article(idx: int, *, hours_ago: float = 0.0) -> RawArticle:
    return RawArticle(
        source_type=SourceType.RSS,
        source_name=f"source-{idx}",
        title=f"Article {idx}",
        url=f"https://example.com/{idx}",
        published_at=_NOW - timedelta(hours=hours_ago),
        raw_text=f"Body of article {idx}",
    )


class FakeEmbedder:
    """Deterministic stand-in for a real embedding model: each text is
    mapped to a fixed, pre-normalized vector via ``vectors``, so cluster
    membership is fully controlled by the test instead of a live model."""

    def __init__(self, vectors: dict[str, np.ndarray]) -> None:
        self._vectors = vectors

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.array([self._vectors[text] for text in texts])


def _text_for(article: RawArticle) -> str:
    return f"{article.title}\n{article.raw_text}"[:2000]


def test_near_duplicates_collapse_into_one_cluster():
    a, b, c = _article(1), _article(2), _article(3)
    # a and b point in (almost) the same direction; c is orthogonal.
    vectors = {
        _text_for(a): np.array([1.0, 0.0]),
        _text_for(b): np.array([0.99, 0.14]),
        _text_for(c): np.array([0.0, 1.0]),
    }
    clusters = deduplicate(
        [a, b, c], FakeEmbedder(vectors), similarity_threshold=0.9, window_hours=48
    )
    assert len(clusters) == 2
    sizes = sorted(len(cl.members) for cl in clusters)
    assert sizes == [1, 2]


def test_distinct_stories_stay_separate():
    a, b = _article(1), _article(2)
    vectors = {
        _text_for(a): np.array([1.0, 0.0]),
        _text_for(b): np.array([0.0, 1.0]),
    }
    clusters = deduplicate([a, b], FakeEmbedder(vectors), similarity_threshold=0.9, window_hours=48)
    assert len(clusters) == 2


def test_articles_outside_window_are_dropped():
    fresh = _article(1, hours_ago=1)
    stale = _article(2, hours_ago=72)
    vectors = {
        _text_for(fresh): np.array([1.0, 0.0]),
        _text_for(stale): np.array([0.0, 1.0]),
    }
    clusters = deduplicate(
        [fresh, stale], FakeEmbedder(vectors), similarity_threshold=0.9, window_hours=48
    )
    assert len(clusters) == 1
    assert clusters[0].representative.url == fresh.url


def test_empty_input_returns_empty_list():
    assert deduplicate([], FakeEmbedder({}), similarity_threshold=0.9, window_hours=48) == []


def test_representative_is_earliest_published_in_cluster():
    older = _article(1, hours_ago=5)
    newer = _article(2, hours_ago=1)
    vectors = {
        _text_for(older): np.array([1.0, 0.0]),
        _text_for(newer): np.array([0.99, 0.14]),
    }
    clusters = deduplicate(
        [newer, older], FakeEmbedder(vectors), similarity_threshold=0.9, window_hours=48
    )
    assert len(clusters) == 1
    assert clusters[0].representative.url == older.url
