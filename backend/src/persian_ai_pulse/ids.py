"""Stable identity helpers.

Article IDs must survive re-runs of the pipeline: the same story fetched
today and again tomorrow (e.g. because a source re-publishes its feed) has to
collapse to the same ID, otherwise the JSON store grows duplicates forever.
We derive IDs from a normalized URL rather than an incrementing counter or a
timestamp, both of which are position- and time-dependent and were called out
as a correctness risk during the architecture review.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

_TRACKING_PARAM_RE = re.compile(
    r"^(utm_|fbclid$|gclid$|ref$|source$|igshid$)", re.IGNORECASE
)


def normalize_url(url: str) -> str:
    """Lowercase the host, strip fragments/tracking params/trailing slash so
    that visually-identical URLs hash to the same value."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"

    kept_query = [
        kv
        for kv in parts.query.split("&")
        if kv and not _TRACKING_PARAM_RE.match(kv.split("=", 1)[0])
    ]
    query = "&".join(sorted(kept_query))

    return urlunsplit((scheme, netloc, path, query, ""))


def article_id(url: str) -> str:
    """A short, stable, filesystem- and JSON-key-safe article ID."""
    digest = hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
    return digest[:16]
