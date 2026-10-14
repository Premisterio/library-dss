"""Runtime configuration, read from environment variables only (12-factor)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    environment: Literal["dev", "test", "prod"] = "dev"
    database_url: str = Field(
        description="SQLAlchemy URL, e.g. postgresql+psycopg://user:pw@host/db"
    )
    # No default on purpose: the app refuses to start without a real secret.
    secret_key: SecretStr = Field(min_length=32)
    cors_origins: list[str] = Field(
        default_factory=list,
        description="Allowed browser origins when the frontend is served from another domain.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Authentication
    access_token_minutes: int = Field(default=15, ge=1)
    refresh_token_days: int = Field(default=14, ge=1)
    allow_registration: bool = Field(
        default=True, description="Disable in production; create accounts with `dss create-user`."
    )
    cookie_secure: bool = Field(default=True, description="False only for plain-HTTP local dev.")
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Datasets and background jobs
    max_upload_mb: int = Field(default=150, ge=1, description="Uncompressed JSON size limit.")
    worker_poll_seconds: float = Field(default=1.0, gt=0)
    job_stale_seconds: int = Field(
        default=300, ge=10, description="Running jobs without a heartbeat this long are failed."
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
