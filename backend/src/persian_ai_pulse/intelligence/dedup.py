"""Near-duplicate detection via embedding similarity clustering.

Multiple sources frequently cover the same underlying story (a model launch
picked up by three newsletters and a lab blog). Left unclustered, the digest
would repeat itself; naive exact-text dedup would miss paraphrased coverage.
Embedding-based clustering catches both.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

import numpy as np

from persian_ai_pulse.schemas import RawArticle

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """Anything that maps texts to comparable vectors. Implementations
    should return L2-normalized rows so a plain dot product is cosine
    similarity — ``SentenceTransformerEmbedder`` does this via
    ``normalize_embeddings=True``."""

    def embed(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Default embedder: a small multilingual model that handles Persian and
    English well enough to cluster cross-language coverage of the same
    story. Loaded lazily so importing this module doesn't require
    ``sentence-transformers`` unless dedup is actually run."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None

    def _ensure_loaded(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is not installed; install with "
                    "`pip install 'persian-ai-pulse[intelligence]'`"
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        model = self._ensure_loaded()
        return np.asarray(model.encode(texts, normalize_embeddings=True))


@dataclass
class ArticleCluster:
    representative: RawArticle
    members: list[RawArticle] = field(default_factory=list)


def _article_text(article: RawArticle) -> str:
    return f"{article.title}\n{article.raw_text}"[:2000]


def deduplicate(
    articles: list[RawArticle],
    embedder: Embedder,
    *,
    similarity_threshold: float = 0.86,
    window_hours: int = 48,
) -> list[ArticleCluster]:
    """Greedy single-pass clustering, oldest-first: each article joins the
    most similar existing cluster if it clears ``similarity_threshold``,
    otherwise it starts a new one. The first (earliest-published) article in
    a cluster is kept as the representative; the rest are recorded as
    ``members`` for provenance/attribution.

    Only articles inside ``window_hours`` are clustered. Without this bound,
    embedding cost grows with the entire historical archive on every run —
    called out explicitly as a scaling risk during the architecture review.
    """
    if not articles:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    recent = [a for a in articles if a.published_at >= cutoff]
    dropped = len(articles) - len(recent)
    if dropped:
        logger.info("dedup: dropping %d articles older than the %dh window", dropped, window_hours)

    recent.sort(key=lambda a: a.published_at)
    if not recent:
        return []

    embeddings = embedder.embed([_article_text(a) for a in recent])

    clusters: list[ArticleCluster] = []
    centroids: list[np.ndarray] = []

    for article, embedding in zip(recent, embeddings):
        best_idx, best_score = -1, -1.0
        for idx, centroid in enumerate(centroids):
            score = float(np.dot(embedding, centroid))
            if score > best_score:
                best_idx, best_score = idx, score

        if best_idx >= 0 and best_score >= similarity_threshold:
            cluster = clusters[best_idx]
            cluster.members.append(article)
            # Running average keeps the centroid representative as more
            # near-duplicates join, without re-embedding the whole cluster.
            n = len(cluster.members)
            centroids[best_idx] = (centroids[best_idx] * (n - 1) + embedding) / n
        else:
            clusters.append(ArticleCluster(representative=article, members=[article]))
            centroids.append(embedding)

    logger.info("dedup: %d articles -> %d clusters", len(recent), len(clusters))
    return clusters
