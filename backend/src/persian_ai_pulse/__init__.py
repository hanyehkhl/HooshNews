"""Persian AI Pulse — modular ingestion → intelligence → publish pipeline.

The package is split into three independent layers, each usable on its own:

- ``persian_ai_pulse.ingest``       — pull raw articles from RSS/arXiv/Telegram.
- ``persian_ai_pulse.intelligence`` — dedupe, summarize (Persian), rank, and turn
  the day's top stories into an audio digest script + MP3.
- ``persian_ai_pulse.publish``      — write the git-as-database JSON files and
  push the daily digest to Telegram.

See ``cli.py`` for the command-line entrypoints that wire the layers together,
and the top-level README for the end-to-end architecture.
"""

__version__ = "0.1.0"
