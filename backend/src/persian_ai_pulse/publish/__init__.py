"""Publish layer: the git-as-a-database JSON store the frontend reads, and
the Telegram bot dispatcher. Kept independent of each other — a Telegram
outage never blocks the site from publishing, and vice versa."""
