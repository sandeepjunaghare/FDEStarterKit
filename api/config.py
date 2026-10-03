"""Settings from the environment: root `.env` locally, Render env vars in the cloud."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env for local runs. Absent inside the container — real env vars win there.
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    database_url: str
    # Small pool: the Supabase session pooler holds one server connection per client connection.
    db_pool_min: int = 1
    db_pool_max: int = 5
    db_timeout_s: float = 10.0


@lru_cache
def get_settings() -> Settings:
    """Load settings once; lazy so importing the app never requires DATABASE_URL."""
    return Settings()
