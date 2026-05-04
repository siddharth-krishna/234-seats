"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    database_url: str = "sqlite:///./234seats.db"
    secret_key: str = "change-me-in-production"
    provisional_results_api_token: str | None = None
    debug: bool = True


settings = Settings()
