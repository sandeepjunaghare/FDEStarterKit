"""Settings from the environment: root `.env` locally, Render env vars in the cloud."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root .env for local runs. Absent inside the container — real env vars win there.
ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # hide_input_in_errors: a rejected DATABASE_URL contains the password; keep it out of logs.
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore", hide_input_in_errors=True)

    database_url: str
    # Small pool: the Supabase session pooler holds one server connection per client connection.
    db_pool_min: int = 1
    db_pool_max: int = 5
    db_timeout_s: float = 10.0

    @field_validator("database_url")
    @classmethod
    def _database_url_is_a_real_url(cls, v: str) -> str:
        """Fail at startup on a malformed URL: a config mistake, unlike a DB outage (/health/db).

        Catches the paste errors seen when setting it in a dashboard. Messages never echo the value.
        """
        v = v.strip()
        if v.upper().startswith("DATABASE_URL="):
            raise ValueError("value includes the 'DATABASE_URL=' prefix; set only the URL")
        if v[:1] in ("'", '"'):
            raise ValueError("value is wrapped in quotes; remove them")
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("must start with postgresql:// (Supabase session pooler URL)")
        if "<" in v or ">" in v:
            raise ValueError("still contains a <placeholder>; paste the real URL")
        return v


@lru_cache
def get_settings() -> Settings:
    """Load settings once; lazy so importing the app never requires DATABASE_URL."""
    # Fields come from env/.env at runtime, which pyright can't see.
    return Settings()  # pyright: ignore[reportCallIssue]
