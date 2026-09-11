"""A small retry-with-backoff decorator.

Three call sites in this codebase (RSS/arXiv fetch, LLM calls, Telegram
publish) all want the same thing: retry a flaky I/O call a few times with
exponential backoff + jitter. That's a ~30-line utility, not a reason to pull
in a whole dependency — so it's implemented here instead of via ``tenacity``,
keeping the core dependency list one package smaller.
"""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry_with_backoff(
    *,
    exceptions: tuple[type[BaseException], ...],
    attempts: int = 3,
    base_delay_s: float = 1.0,
    max_delay_s: float = 10.0,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry the wrapped call up to ``attempts`` times when it raises one of
    ``exceptions``, sleeping with exponential backoff (doubling each time,
    capped at ``max_delay_s``) plus up to 10% jitter to avoid thundering-herd
    retries. Re-raises the final exception if every attempt fails; any
    exception not in ``exceptions`` propagates immediately without retrying.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == attempts:
                        break
                    delay = min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))
                    delay += random.uniform(0, delay * 0.1)
                    logger.warning(
                        "%s failed (attempt %d/%d): %s; retrying in %.1fs",
                        func.__qualname__,
                        attempt,
                        attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
