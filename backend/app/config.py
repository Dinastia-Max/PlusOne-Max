from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://plusone:plusone@localhost:5432/plusone"
    max_bot_token: str = ""
    max_mini_app_url: str = ""
    max_auth_max_age_seconds: int = 3600
    cors_origins: str = (
        "http://localhost:8080,http://localhost:8443,http://localhost:5173"
    )

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
