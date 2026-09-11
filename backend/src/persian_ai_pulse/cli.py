"""Command-line entrypoints wiring the three layers together.

Each subcommand maps to one GitHub Actions step (see
``.github/workflows/pipeline.yml``), which keeps CI logs granular and lets
any single stage be re-run in isolation during development:

    pap ingest            # sources -> .pipeline_cache/raw_articles.json
    pap process           # dedup + summarize + rank -> .pipeline_cache/processed_articles.json
    pap publish-site       # write today's data/days/<date>.json + index.json (+ audio)
    pap publish-telegram   # send today's digest to the configured Telegram chat
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from persian_ai_pulse.config import get_settings
from persian_ai_pulse.ingest.pipeline import apply_coverage_gate, build_sources_from_config, run_ingestion
from persian_ai_pulse.intelligence.audio_digest import render_audio_digest
from persian_ai_pulse.intelligence.dedup import SentenceTransformerEmbedder, deduplicate
from persian_ai_pulse.intelligence.llm_provider import build_default_provider as build_llm_provider
from persian_ai_pulse.intelligence.summarizer import select_top_articles, summarize_articles
from persian_ai_pulse.intelligence.tts_provider import build_default_provider as build_tts_provider
from persian_ai_pulse.publish.json_store import JsonStore
from persian_ai_pulse.publish.telegram_publisher import TelegramPublisher
from persian_ai_pulse.schemas import ProcessedArticle, RawArticle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_CACHE_DIR = Path(".pipeline_cache")
_RAW_CACHE = _CACHE_DIR / "raw_articles.json"
_PROCESSED_CACHE = _CACHE_DIR / "processed_articles.json"


def _write_json_cache(path: Path, models: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(model.model_dump_json()) for model in models]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _cmd_ingest(args: argparse.Namespace) -> None:
    settings = get_settings()
    sources = build_sources_from_config(Path(args.config), settings)
    if not sources:
        logger.warning("ingest: no sources configured; nothing to fetch")

    raw_articles = run_ingestion(sources, max_workers=args.max_workers)
    gated = apply_coverage_gate(raw_articles, max_per_source=args.max_per_source)

    _write_json_cache(_RAW_CACHE, gated)
    logger.info("ingest: %d raw -> %d after coverage gate -> %s", len(raw_articles), len(gated), _RAW_CACHE)


def _cmd_process(args: argparse.Namespace) -> None:
    settings = get_settings()
    raw_payload = json.loads(_RAW_CACHE.read_text(encoding="utf-8"))
    raw_articles = [RawArticle.model_validate(item) for item in raw_payload]

    embedder = SentenceTransformerEmbedder(settings.embedding_model_name)
    clusters = deduplicate(
        raw_articles,
        embedder,
        similarity_threshold=settings.dedup_similarity_threshold,
        window_hours=settings.dedup_window_hours,
    )
    representatives = [cluster.representative for cluster in clusters]
    logger.info("process: %d raw -> %d after dedup", len(raw_articles), len(representatives))

    provider = build_llm_provider(settings.llm)
    processed = summarize_articles(representatives, provider)
    top = select_top_articles(processed, limit=settings.max_articles_per_digest)

    _write_json_cache(_PROCESSED_CACHE, top)
    logger.info("process: %d summarized -> %d selected -> %s", len(processed), len(top), _PROCESSED_CACHE)


def _cmd_publish_site(args: argparse.Namespace) -> None:
    settings = get_settings()
    processed_payload = json.loads(_PROCESSED_CACHE.read_text(encoding="utf-8"))
    articles = [ProcessedArticle.model_validate(item) for item in processed_payload]
    today = date.today().isoformat()

    audio_url: str | None = None
    if args.with_audio and articles:
        tts_provider = build_tts_provider(settings.tts)
        audio_path = settings.media_dir / f"digest-{today}.mp3"
        render_audio_digest(
            articles,
            tts_provider,
            digest_date=date.today(),
            out_path=audio_path,
            max_chars=settings.max_audio_script_chars,
        )
        audio_url = f"/media/{audio_path.name}"
    elif args.with_audio:
        logger.warning("publish-site: --with-audio set but there are no articles; skipping audio")

    store = JsonStore(settings.data_dir)
    digest = store.upsert_day(today, articles, daily_audio_url=audio_url)
    logger.info(
        "publish-site: date=%s articles=%d audio=%s", digest.date, len(digest.articles), audio_url
    )


def _cmd_publish_telegram(args: argparse.Namespace) -> None:
    settings = get_settings()
    store = JsonStore(settings.data_dir)
    today = date.today().isoformat()
    digest = store.load_day(today)
    if digest is None:
        logger.warning("publish-telegram: no digest found for %s; nothing to publish", today)
        return

    publisher = TelegramPublisher(settings.telegram_publish)
    publisher.send_text_digest(digest)

    if digest.daily_audio_url:
        audio_path = settings.media_dir / Path(digest.daily_audio_url).name
        if audio_path.exists():
            publisher.send_audio_digest(digest, audio_path)
        else:
            logger.warning("publish-telegram: audio file %s not found; sending text only", audio_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pap", description="Persian AI Pulse pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Fetch raw articles from configured sources")
    ingest_parser.add_argument("--config", default="backend/config/sources.json")
    ingest_parser.add_argument("--max-workers", type=int, default=8)
    ingest_parser.add_argument("--max-per-source", type=int, default=15)
    ingest_parser.set_defaults(func=_cmd_ingest)

    process_parser = subparsers.add_parser(
        "process", help="Dedup, Persian-summarize, and rank the ingested articles"
    )
    process_parser.set_defaults(func=_cmd_process)

    publish_site_parser = subparsers.add_parser(
        "publish-site", help="Write today's digest (and optional audio) to the JSON store"
    )
    publish_site_parser.add_argument("--with-audio", action="store_true")
    publish_site_parser.set_defaults(func=_cmd_publish_site)

    publish_tg_parser = subparsers.add_parser(
        "publish-telegram", help="Send today's already-published digest to Telegram"
    )
    publish_tg_parser.set_defaults(func=_cmd_publish_telegram)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception:
        logger.exception("command %r failed", args.command)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
