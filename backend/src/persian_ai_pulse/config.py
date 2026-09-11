"""Centralized, environment-driven configuration.

Every layer reads its knobs from a single ``Settings`` instance instead of
calling ``os.environ`` directly. This keeps provider choice (which LLM, which
TTS engine, which data sources) declarative and makes the whole pipeline
testable by constructing a ``Settings`` object with overrides — no env-var
patching required.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Any OpenAI-Chat-Completions-compatible endpoint works here: OpenAI
    itself, Groq, Together.ai, OpenRouter, or a locally hosted vLLM/Ollama
    server — swap ``base_url`` and ``model`` and nothing else changes."""

    model_config = SettingsConfigDict(env_prefix="PAP_LLM_", extra="ignore")

    api_key: str = Field(default="", description="API key for the LLM provider.")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible base URL.",
    )
    model: str = Field(default="gpt-4o-mini")
    request_timeout_s: float = Field(default=60.0)
    max_retries: int = Field(default=3)


class TTSSettings(BaseSettings):
    """Default engine is edge-tts (free, good-quality Persian neural voices).
    Set ``provider=openai`` to use a paid OpenAI-compatible TTS endpoint
    instead — useful if edge-tts voices are ever retired or blocked."""

    model_config = SettingsConfigDict(env_prefix="PAP_TTS_", extra="ignore")

    provider: str = Field(default="edge", pattern="^(edge|openai)$")
    voice: str = Field(default="fa-IR-DilaraNeural")
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_model: str = Field(default="gpt-4o-mini-tts")


class TelegramIngestSettings(BaseSettings):
    """Credentials for *reading* channels via a user session (Telethon).
    Deliberately separate from ``TelegramPublishSettings`` — ingestion needs
    a full user session, publishing only needs a bot token, and mixing the
    two means a bot-token rotation can silently break scraping and vice
    versa."""

    model_config = SettingsConfigDict(env_prefix="PAP_TG_INGEST_", extra="ignore")

    api_id: int | None = Field(default=None)
    api_hash: str = Field(default="")
    session_string: str = Field(default="")
    channels: list[str] = Field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_id and self.api_hash and self.session_string)


class TelegramPublishSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAP_TG_PUBLISH_", extra="ignore")

    bot_token: str = Field(default="")
    chat_id: str = Field(default="")

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


class Settings(BaseSettings):
    """Top-level settings. Nested groups are composed rather than flattened
    so each layer only needs to import the slice it actually uses."""

    model_config = SettingsConfigDict(env_prefix="PAP_", extra="ignore")

    # Both live under frontend/public/ by default so the static site can
    # serve them directly at /data/... and /media/... with no separate data
    # service — the whole point of the git-as-a-database approach.
    data_dir: Path = Field(default=Path("frontend/public/data"))
    media_dir: Path = Field(default=Path("frontend/public/media"))
    timezone: str = Field(default="UTC")

    # Dedup / clustering
    dedup_similarity_threshold: float = Field(default=0.86)
    dedup_window_hours: int = Field(default=48)
    embedding_model_name: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2"
    )

    # Content selection
    max_articles_per_digest: int = Field(default=20)
    max_audio_script_chars: int = Field(default=4000)

    llm: LLMSettings = Field(default_factory=LLMSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    telegram_ingest: TelegramIngestSettings = Field(default_factory=TelegramIngestSettings)
    telegram_publish: TelegramPublishSettings = Field(default_factory=TelegramPublishSettings)


def get_settings() -> Settings:
    """Factory instead of a module-level singleton, so tests can construct
    an isolated ``Settings()`` without env leaking between them."""
    return Settings()
