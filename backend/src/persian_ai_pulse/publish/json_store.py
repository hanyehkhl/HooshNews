"""Git-as-a-database persistence.

One JSON file per day (``data/days/<date>.json``) plus a small manifest
(``data/index.json``), instead of a single ever-growing ``releases.json``.
The frontend fetches the cheap index first, then only the day(s) it actually
needs — this is what keeps page-load cost flat as the archive grows, which
was flagged as a scaling risk in the architecture review.

All writes are atomic (write-temp-then-rename), so a crashed run never
leaves the frontend or the next pipeline run looking at a half-written file.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from persian_ai_pulse.schemas import DailyDigest, DigestIndex, DigestIndexEntry, ProcessedArticle

logger = logging.getLogger(__name__)

_DAYS_SUBDIR = "days"
_INDEX_FILENAME = "index.json"


class JsonStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.days_dir = data_dir / _DAYS_SUBDIR
        self.index_path = data_dir / _INDEX_FILENAME

    def _day_path(self, day: str) -> Path:
        return self.days_dir / f"{day}.json"

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)  # atomic rename on POSIX and Windows (py3.3+)

    def load_day(self, day: str) -> DailyDigest | None:
        path = self._day_path(day)
        if not path.exists():
            return None
        return DailyDigest.model_validate_json(path.read_text(encoding="utf-8"))

    def upsert_day(
        self,
        day: str,
        new_articles: list[ProcessedArticle],
        *,
        daily_audio_url: str | None = None,
    ) -> DailyDigest:
        """Merge ``new_articles`` into the existing day file by article id —
        an id already present is replaced, not duplicated — so re-running
        the pipeline for the same day (e.g. a manual re-trigger) is
        idempotent instead of growing the file."""
        existing = self.load_day(day)
        merged: dict[str, ProcessedArticle] = {a.id: a for a in existing.articles} if existing else {}
        for article in new_articles:
            merged[article.id] = article

        digest = DailyDigest(
            date=day,
            generated_at=datetime.now(timezone.utc),
            daily_audio_url=daily_audio_url or (existing.daily_audio_url if existing else None),
            articles=sorted(merged.values(), key=lambda a: a.importance_score, reverse=True),
        )
        self._atomic_write(self._day_path(day), digest.model_dump_json(indent=2))
        self._refresh_index_entry(digest)
        logger.info("published day=%s articles=%d", day, len(digest.articles))
        return digest

    def load_index(self) -> DigestIndex:
        if not self.index_path.exists():
            return DigestIndex(updated_at=datetime.now(timezone.utc), days=[])
        return DigestIndex.model_validate_json(self.index_path.read_text(encoding="utf-8"))

    def _refresh_index_entry(self, digest: DailyDigest) -> None:
        index = self.load_index()
        entries = [e for e in index.days if e.date != digest.date]
        entries.append(
            DigestIndexEntry(
                date=digest.date,
                article_count=len(digest.articles),
                has_audio=digest.daily_audio_url is not None,
            )
        )
        entries.sort(key=lambda e: e.date, reverse=True)
        self._atomic_write(
            self.index_path,
            DigestIndex(updated_at=datetime.now(timezone.utc), days=entries).model_dump_json(indent=2),
        )

    def rebuild_index(self) -> DigestIndex:
        """Recompute the index from whatever day files exist on disk.
        Useful for recovery if the index and day files ever drift apart
        (e.g. a manual edit or a merge conflict resolved by hand)."""
        entries: list[DigestIndexEntry] = []
        if self.days_dir.exists():
            for path in sorted(self.days_dir.glob("*.json")):
                digest = DailyDigest.model_validate_json(path.read_text(encoding="utf-8"))
                entries.append(
                    DigestIndexEntry(
                        date=digest.date,
                        article_count=len(digest.articles),
                        has_audio=digest.daily_audio_url is not None,
                    )
                )
        entries.sort(key=lambda e: e.date, reverse=True)
        index = DigestIndex(updated_at=datetime.now(timezone.utc), days=entries)
        self._atomic_write(self.index_path, index.model_dump_json(indent=2))
        return index
