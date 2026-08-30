from __future__ import annotations

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+asyncpg://user:password@localhost:5432/analytics_db"
    )
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Same database, driver swapped for the sync Celery worker."""
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg")


settings = Settings()
