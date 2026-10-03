import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

import main


@pytest.fixture
def client():
    """Client without the lifespan: no pool, no network. Each test stubs check_db."""
    main.app.state.pool = object()
    return TestClient(main.app)


def stub_check_db(monkeypatch, result=None, raises=None):
    async def fake(_pool):
        if raises:
            raise raises
        return result

    monkeypatch.setattr(main, "check_db", fake)


def test_health_is_ok_without_db(client, monkeypatch):
    stub_check_db(monkeypatch, raises=AssertionError("/health must not touch the DB"))
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_db_ok(client, monkeypatch):
    stub_check_db(monkeypatch, result="0.8.2")
    r = client.get("/health/db")
    assert r.status_code == 200
    assert r.json() == {"db": "ok", "pgvector": "0.8.2"}


def test_health_db_pgvector_missing(client, monkeypatch):
    stub_check_db(monkeypatch, result=None)
    r = client.get("/health/db")
    assert r.status_code == 503
    assert r.json() == {"db": "ok", "pgvector": "missing"}


@pytest.mark.parametrize(
    "err", [PoolTimeout("couldn't get a connection"), psycopg.OperationalError("host db.x.supabase.co")]
)
def test_health_db_unreachable_hides_details(client, monkeypatch, err):
    stub_check_db(monkeypatch, raises=err)
    r = client.get("/health/db")
    assert r.status_code == 503
    assert r.json() == {"db": "error", "detail": type(err).__name__}
    assert "supabase" not in r.text


@pytest.mark.integration
def test_health_db_against_supabase():
    """Real lifespan + pool against DATABASE_URL (env or repo-root .env)."""
    from pydantic import ValidationError

    from config import get_settings

    try:
        get_settings()
    except ValidationError:
        pytest.skip("DATABASE_URL not set")
    with TestClient(main.app) as c:
        r = c.get("/health/db")
    assert r.status_code == 200, r.text
    assert r.json()["db"] == "ok"
