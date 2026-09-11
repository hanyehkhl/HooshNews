"""Ingestion layer: turns heterogeneous sources into a flat list of
``RawArticle``. Each source lives in its own module and implements the
``SourceFetcher`` interface, so adding a new source never touches existing
ones — see ``base.py``."""

from persian_ai_pulse.ingest.base import SourceFetcher
from persian_ai_pulse.ingest.pipeline import run_ingestion

__all__ = ["SourceFetcher", "run_ingestion"]
