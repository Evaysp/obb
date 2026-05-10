"""Application config loaded from environment variables.

All settings flow through this module — never read os.environ directly elsewhere.
See CONVENTIONS.md §4 for naming rules (SCREAMING_SNAKE_CASE with prefix groups).
"""

from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── app ────────────────────────────────────
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    app_cors_origins: str = Field(default="http://localhost:3000", alias="APP_CORS_ORIGINS")

    # ─── database ───────────────────────────────
    db_url: str = Field(alias="DB_URL")
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    # ─── redis ──────────────────────────────────
    redis_url: str = Field(alias="REDIS_URL")

    # ─── security ───────────────────────────────
    cookie_enc_key: str = Field(alias="COOKIE_ENC_KEY")
    session_secret: str = Field(alias="SESSION_SECRET")

    # ─── fetcher ────────────────────────────────
    fetch_user_agent: str = Field(alias="FETCH_USER_AGENT")
    fetch_timeout_seconds: int = Field(default=30, alias="FETCH_TIMEOUT_SECONDS")
    fetch_default_rate_per_min: int = Field(default=6, alias="FETCH_DEFAULT_RATE_PER_MIN")

    # ─── dev user (auth deferred) ───────────────
    dev_user_email: str = Field(alias="DEV_USER_EMAIL")
    dev_user_id: UUID = Field(alias="DEV_USER_ID")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.app_cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
