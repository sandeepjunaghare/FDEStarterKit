import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.errors import UndefinedTable
from psycopg_pool import PoolTimeout

import main
from db import SmokeCheckError


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
    "err",
    [PoolTimeout("couldn't get a connection"), psycopg.OperationalError("host db.x.supabase.co")],
)
def test_health_db_unreachable_hides_details(client, monkeypatch, err):
    stub_check_db(monkeypatch, raises=err)
    r = client.get("/health/db")
    assert r.status_code == 503
    assert r.json() == {"db": "error", "detail": type(err).__name__}
    assert "supabase" not in r.text


def stub_smoke(monkeypatch, result=0.0, raises=None):
    async def fake(_pool):
        if raises:
            raise raises
        return result

    monkeypatch.setattr(main, "smoke_roundtrip", fake)


def test_smoke_ok(client, monkeypatch):
    stub_smoke(monkeypatch, result=0.0)
    r = client.post("/smoke")
    assert r.status_code == 200
    assert r.json() == {
        "smoke": "ok",
        "write": "ok",
        "read": "ok",
        "vector_search": "ok",
        "distance": 0.0,
    }


@pytest.mark.parametrize(
    "err",
    [UndefinedTable('relation "smoke_checks" does not exist'), SmokeCheckError("wrong row")],
)
def test_smoke_failure_is_503_with_class_only(client, monkeypatch, err):
    stub_smoke(monkeypatch, raises=err)
    r = client.post("/smoke")
    assert r.status_code == 503
    assert r.json() == {"smoke": "error", "detail": type(err).__name__}


def test_smoke_rejects_get(client):
    assert client.get("/smoke").status_code == 405


@pytest.fixture
def live_client():
    """Real lifespan + pool against DATABASE_URL (env or repo-root .env)."""
    from pydantic import ValidationError

    from config import get_settings

    try:
        get_settings()
    except ValidationError:
        pytest.skip("DATABASE_URL not set")
    with TestClient(main.app) as c:
        yield c


@pytest.mark.integration
def test_health_db_against_supabase(live_client):
    r = live_client.get("/health/db")
    assert r.status_code == 200, r.text
    assert r.json()["db"] == "ok"


@pytest.mark.integration
def test_smoke_against_supabase(live_client):
    """Needs migrations applied (uv run python -m db.migrate)."""
    r = live_client.post("/smoke")
    assert r.status_code == 200, r.text
    assert r.json()["distance"] == pytest.approx(0.0)


@pytest.fixture
def settings_env(monkeypatch):
    """Fresh settings from env only (CI has no .env); cache cleared before and after."""
    from config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_version_reports_render_commit(client, settings_env):
    settings_env.setenv("RENDER_GIT_COMMIT", "7e392b9abc")
    r = client.get("/version")
    assert r.status_code == 200
    assert r.json() == {"commit": "7e392b9abc"}


def test_version_is_local_outside_render(client, settings_env):
    settings_env.delenv("RENDER_GIT_COMMIT", raising=False)
    assert client.get("/version").json() == {"commit": "local"}
