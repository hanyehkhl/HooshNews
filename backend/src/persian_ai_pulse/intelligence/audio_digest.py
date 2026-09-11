"""Builds the daily 1-3 minute Persian audio digest: a short spoken script
from the day's top-ranked articles, rendered to MP3 via the configured
``TTSProvider``.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from persian_ai_pulse.intelligence.tts_provider import TTSProvider
from persian_ai_pulse.schemas import ProcessedArticle

_INTRO_TEMPLATE = "این پادکست خبری هوش مصنوعی برای تاریخ {date} است. مهم‌ترین رویدادها را با هم مرور می‌کنیم."
_OUTRO = "برای جزئیات بیشتر و منابع کامل هر خبر، به سایت Persian AI Pulse سر بزنید."
_ITEM_SEP = "\n\n"


def build_audio_script(
    articles: list[ProcessedArticle],
    *,
    digest_date: date,
    max_chars: int = 4000,
) -> str:
    """Concatenates intro + per-article blurbs (in ranked order) + outro,
    trimmed to ``max_chars`` so the resulting audio stays in the 1-3 minute
    range the product spec calls for (roughly 800-900 Persian chars/minute
    of natural speech)."""
    parts = [_INTRO_TEMPLATE.format(date=digest_date.isoformat())]

    for article in articles:
        blurb = f"{article.title_fa}. {article.summary_fa} {article.why_it_matters}".strip()
        candidate = _ITEM_SEP.join([*parts, blurb, _OUTRO])
        if len(candidate) > max_chars:
            break
        parts.append(blurb)

    parts.append(_OUTRO)
    return _ITEM_SEP.join(parts)


def render_audio_digest(
    articles: list[ProcessedArticle],
    provider: TTSProvider,
    *,
    digest_date: date,
    out_path: Path,
    max_chars: int = 4000,
) -> str:
    """Builds the script and renders it to ``out_path``. Returns the script
    text as well, since ``publish`` layers may want to log/store it
    alongside the audio for transparency/debugging."""
    script = build_audio_script(articles, digest_date=digest_date, max_chars=max_chars)
    provider.synthesize(script, out_path)
    return script
