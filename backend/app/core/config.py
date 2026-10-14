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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
