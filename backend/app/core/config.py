"""Load all secrets and tunables from environment variables. Nothing is hard-coded in routers."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-level config. Shop display name still comes from the settings table."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TECH TOYS"
    environment: str = "development"
    demo_mode: bool = True
    seed_on_startup: bool = True
    admin_password: str = ""
    seed_token: str = ""
    secret_key: str = "change-me-to-a-long-random-string"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    database_url: str = "sqlite:///./shop.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: str = "./uploads"
    anthropic_api_key: str = ""
    otp_provider: str = ""

    def cors_origin_list(self) -> List[str]:
        """Split the comma-separated CORS string into a list FastAPI can use."""
        parts: List[str] = []
        for raw in self.cors_origins.split(","):
            item = raw.strip()
            if item != "":
                parts.append(item)
        return parts

    def sqlalchemy_database_url(self) -> str:
        """Make common hosted Postgres URLs use the installed psycopg driver."""
        if self.database_url.startswith("postgres://"):
            return "postgresql+psycopg://" + self.database_url[len("postgres://"):]
        if self.database_url.startswith("postgresql://"):
            return "postgresql+psycopg://" + self.database_url[len("postgresql://"):]
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """Cache settings so we do not re-read the env on every request."""
    return Settings()
