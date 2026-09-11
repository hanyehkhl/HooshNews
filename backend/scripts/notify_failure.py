#!/usr/bin/env python3
"""Tiny ops script used only by CI's failure step (see
``.github/workflows/pipeline.yml``). Kept separate from ``cli.py`` because
this is an operational concern (alert-on-CI-failure), not part of the
library's public pipeline API.

Usage: python backend/scripts/notify_failure.py "<message>"

Reads PAP_TG_PUBLISH_BOT_TOKEN / PAP_TG_PUBLISH_CHAT_ID from the
environment. Silently does nothing if either is unset, so forks/local runs
without Telegram configured don't fail on this step.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from persian_ai_pulse.publish.telegram_publisher import notify_failure  # noqa: E402


def main() -> int:
    message = sys.argv[1] if len(sys.argv) > 1 else "(no message provided)"
    bot_token = os.environ.get("PAP_TG_PUBLISH_BOT_TOKEN", "")
    chat_id = os.environ.get("PAP_TG_PUBLISH_CHAT_ID", "")

    if not bot_token or not chat_id:
        print("notify_failure: Telegram admin alert not configured; skipping", file=sys.stderr)
        return 0

    notify_failure(bot_token, chat_id, message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
