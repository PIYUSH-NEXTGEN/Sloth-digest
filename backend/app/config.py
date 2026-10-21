"""Env-driven configuration for SlothDigest (AGENTS.md 7.5).

All values can be overridden through environment variables prefixed with
``SLOTH_``. Nothing here performs network I/O; network-touching integrations
are gated behind empty-by-default keys.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SLOTH_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    model: str = Field(default="gemma3:4b", description="Ollama model tag (SLOTH_MODEL).")
    ollama_url: str = Field(default="http://localhost:11434")
    context_tokens: int = Field(
        default=16384,
        description="Ollama num_ctx; prompt larger than this gets silently truncated (SLOTH_CONTEXT_TOKENS).",
    )
    embed_model: str = Field(
        default="nomic-embed-text", description="Local Ollama embedding model (SLOTH_EMBED_MODEL)."
    )
    db_path: str = Field(default="./data/sloth.db")
    drop_folder: str = Field(default="./data/drop")
    digest_time: str = Field(default="06:00", description="Daily schedule, local time HH:MM.")
    user_names: list[str] = Field(default_factory=lambda: ["Your Name", "nickname"])
    vip_people: list[str] = Field(
        default_factory=list, description="Extra important senders (VIP)."
    )
    keywords: list[str] = Field(
        default_factory=list, description="Extra importance keywords beyond the defaults."
    )
    sentry_dsn: str = Field(default="", description="Empty = Sentry disabled.")
    elevenlabs_api_key: str = Field(default="", description="Empty = voice disabled.")
    elevenlabs_voice_id: str = Field(
        default="", description="ElevenLabs voice; empty = bundled default."
    )
    temporal_enabled: bool = Field(default=False)
    desktop_notify: bool = Field(
        default=False, description="Opt-in OS toast after the scheduled digest."
    )

    @property
    def sentry_enabled(self) -> bool:
        return bool(self.sentry_dsn)

    @property
    def voice_enabled(self) -> bool:
        return bool(self.elevenlabs_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
