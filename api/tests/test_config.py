import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import main
from config import Settings, get_settings

GOOD = "postgresql://postgres.abc:s3cretPw@aws-0-us-east-1.pooler.supabase.com:5432/postgres"


@pytest.mark.parametrize(
    "url",
    [GOOD, GOOD + "?sslmode=require", "postgres://u:p@h:5432/db", f"  {GOOD}\n"],
)
def test_accepts_real_urls(url):
    assert Settings(database_url=url).database_url == url.strip()


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (f"DATABASE_URL={GOOD}", "DATABASE_URL="),  # whole .env line pasted (Render, Oct 2)
        (f"'{GOOD}'", "quotes"),
        (f'"{GOOD}"', "quotes"),
        ("postgresql://postgres.<ref>:<password>@h:5432/postgres", "placeholder"),  # Oct 3
        ("mysql://u:p@h/db", "postgresql://"),
        ("", "postgresql://"),
    ],
)
def test_rejects_paste_mistakes_with_a_clear_message(url, message):
    with pytest.raises(ValidationError) as exc:
        Settings(database_url=url)
    assert message in str(exc.value)


def test_error_never_echoes_the_password():
    with pytest.raises(ValidationError) as exc:
        Settings(database_url=f"'{GOOD}'")
    assert "s3cretPw" not in str(exc.value)


def test_app_refuses_to_start_with_a_malformed_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"DATABASE_URL={GOOD}")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError), TestClient(main.app):
            pass
    finally:
        get_settings.cache_clear()
