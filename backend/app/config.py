from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://plusone:plusone@localhost:5432/plusone"
    max_bot_token: str = ""
    max_mini_app_url: str = ""
    max_auth_max_age_seconds: int = 3600
    notification_poll_interval_seconds: float = 10.0
    notification_batch_size: int = 50
    notification_max_attempts: int = 5
    notification_lock_timeout_seconds: int = 300
    notification_retry_delay_seconds: int = 60
    notification_stats_interval_seconds: float = 60.0
    cors_origins: str = (
        "http://localhost:8080,http://localhost:8443,http://localhost:5173"
    )

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        # Render и другие хостинги отдают строку вида postgresql://...
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value.removeprefix(prefix)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
