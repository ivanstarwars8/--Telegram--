"""Application configuration settings using Pydantic."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Centralised configuration for the platform."""

    app_name: str = "FocusOps"
    environment: str = Field("development", regex=r"^(development|staging|production)$")
    secret_key: str = Field("dev-secret", env="SECRET_KEY")
    api_host: str = Field("0.0.0.0")
    api_port: int = Field(8000)

    api_base_url: str = Field("http://api:8000", env="API_BASE_URL")

    postgres_dsn: str = Field("postgresql+asyncpg://focus:focus@localhost:5432/focus", env="POSTGRES_DSN")
    redis_dsn: str = Field("redis://localhost:6379/0", env="REDIS_DSN")

    sentry_dsn: str | None = Field(default=None, env="SENTRY_DSN")

    telegram_bot_token: str = Field("TEST_TOKEN", env="TELEGRAM_BOT_TOKEN")
    telegram_admin_ids: List[int] = Field(default_factory=list, env="TELEGRAM_ADMIN_IDS")

    timezone_default: str = Field("Europe/Moscow")

    celery_broker_url: str = Field("redis://localhost:6379/1", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")

    auto_create_schema: bool = Field(True, env="AUTO_CREATE_SCHEMA")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("telegram_admin_ids", pre=True)
    def _split_admin_ids(cls, value: Any) -> List[int]:  # noqa: D401
        """Parse comma separated admin ids into integer list."""
        if not value:
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        return [int(v.strip()) for v in str(value).split(",") if v.strip()]

    @property
    def celery_config(self) -> Dict[str, Any]:
        return {
            "broker_url": self.celery_broker_url,
            "result_backend": self.celery_result_backend,
            "task_serializer": "json",
            "accept_content": ["json"],
            "result_serializer": "json",
            "timezone": self.timezone_default,
            "enable_utc": True,
        }

    @property
    def root_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
