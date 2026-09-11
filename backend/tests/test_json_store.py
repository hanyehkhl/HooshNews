from datetime import datetime, timezone
from pathlib import Path

from persian_ai_pulse.publish.json_store import JsonStore
from persian_ai_pulse.schemas import ProcessedArticle


def _article(idx: int, *, score: float = 5.0) -> ProcessedArticle:
    return ProcessedArticle(
        id=f"id-{idx}",
        title_fa=f"عنوان {idx}",
        title_en=f"Title {idx}",
        source="Test Source",
        category="Research",
        importance_score=score,
        summary_fa="خلاصه.",
        why_it_matters="چرا مهم است.",
        original_url=f"https://example.com/{idx}",
        tags=["tag"],
        published_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )


def test_upsert_day_then_load_round_trips(tmp_path: Path):
    store = JsonStore(tmp_path)
    digest = store.upsert_day("2026-09-11", [_article(1), _article(2)])

    loaded = store.load_day("2026-09-11")
    assert loaded is not None
    assert loaded.date == digest.date
    assert {a.id for a in loaded.articles} == {"id-1", "id-2"}


def test_upsert_day_is_idempotent_on_article_id(tmp_path: Path):
    store = JsonStore(tmp_path)
    store.upsert_day("2026-09-11", [_article(1, score=5.0)])
    store.upsert_day("2026-09-11", [_article(1, score=9.0)])  # same id, updated score

    loaded = store.load_day("2026-09-11")
    assert loaded is not None
    assert len(loaded.articles) == 1
    assert loaded.articles[0].importance_score == 9.0


def test_upsert_day_merges_rather_than_replaces_other_articles(tmp_path: Path):
    store = JsonStore(tmp_path)
    store.upsert_day("2026-09-11", [_article(1)])
    store.upsert_day("2026-09-11", [_article(2)])

    loaded = store.load_day("2026-09-11")
    assert loaded is not None
    assert {a.id for a in loaded.articles} == {"id-1", "id-2"}


def test_index_reflects_latest_day_state(tmp_path: Path):
    store = JsonStore(tmp_path)
    store.upsert_day("2026-09-10", [_article(1)])
    store.upsert_day("2026-09-11", [_article(2), _article(3)], daily_audio_url="/media/x.mp3")

    index = store.load_index()
    by_date = {entry.date: entry for entry in index.days}
    assert by_date["2026-09-10"].article_count == 1
    assert by_date["2026-09-10"].has_audio is False
    assert by_date["2026-09-11"].article_count == 2
    assert by_date["2026-09-11"].has_audio is True
    # newest first
    assert index.days[0].date == "2026-09-11"


def test_rebuild_index_recovers_from_scratch(tmp_path: Path):
    store = JsonStore(tmp_path)
    store.upsert_day("2026-09-10", [_article(1)])
    store.upsert_day("2026-09-11", [_article(2)])

    store.index_path.unlink()  # simulate a lost/corrupted index
    rebuilt = store.rebuild_index()

    assert {e.date for e in rebuilt.days} == {"2026-09-10", "2026-09-11"}


def test_load_day_returns_none_when_missing(tmp_path: Path):
    store = JsonStore(tmp_path)
    assert store.load_day("2099-01-01") is None


def test_writes_are_atomic_no_tmp_files_left_behind(tmp_path: Path):
    store = JsonStore(tmp_path)
    store.upsert_day("2026-09-11", [_article(1)])

    leftover_tmp_files = list(tmp_path.rglob("*.tmp"))
    assert leftover_tmp_files == []
