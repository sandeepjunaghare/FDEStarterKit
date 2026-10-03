# Task: API skeleton with /health

Goal: a runnable FastAPI service under `api/` (per the CLAUDE.md architecture map) whose
`GET /health` proves the DB path end to end — locally, in Docker, and on Render (stage 5).

## Decisions (assumptions — confirm or change)

- Python 3.12, managed by `uv` (`api/pyproject.toml` + `uv.lock`); run with `uv run`.
- Async stack: FastAPI + `psycopg` 3 `AsyncConnectionPool`, opened/closed in the app lifespan.
- Config via `pydantic-settings`; reads `DATABASE_URL` from env, falling back to the root `.env`.
- Split health (approved): `GET /health` = process up, always 200 `{"status":"ok"}` — Render's health check path.
  `GET /health/db` = deep check (pgvector version via the pool): 200 `{"db":"ok","pgvector":"0.8.2"}`,
  503 if the DB is unreachable or pgvector is missing. Error detail = exception class only (no hostnames leaked).
- Pool opens lazily-tolerant: the app still starts if Supabase is down, so `/health` can report 503
  instead of the container crash-looping.
- Only the files below. No empty `agents/`, `rag/`, `memory/` stubs — those land with real code.

## Plan

- [x] `api/pyproject.toml` — deps: fastapi, uvicorn[standard], psycopg[binary,pool], pgvector, pydantic-settings; dev: pytest, httpx
- [x] `api/config.py` — `Settings` (DATABASE_URL required, POOL_MIN/MAX small for the Supabase pooler)
- [x] `api/db/__init__.py` — pool factory + `check_db()` returning `(ok, pgvector_version | error)`
- [x] `api/main.py` — app with lifespan (pool open/close), `GET /health` and `GET /health/db`
- [x] `api/tests/test_health.py` — unit tests with the DB check stubbed (200 + 503 paths, no network);
      one `@pytest.mark.integration` test against real Supabase, skipped when DATABASE_URL is unset
- [x] `api/Dockerfile` + `api/.dockerignore` — python:3.12-slim + uv, non-root, `uvicorn main:app --port ${PORT:-8000}` (Render sets PORT)
- [x] `docker-compose.yml` (root) — `api` service only for now, `env_file: .env`, port 8000
- [x] Update CLAUDE.md map (`api/tests/`, compose = api only until `ui/` exists) + Commands section

## Verification

- [x] `cd api && uv run pytest` — unit tests pass
- [x] `uv run pytest -m integration` — passes against Supabase
- [x] `uv run uvicorn main:app` → `curl localhost:8000/health/db` returns 200 with pgvector 0.8.2
- [x] `docker compose up --build` → same curl returns 200 from inside the container
- [ ] (you, later) deploy to Render → `curl https://<api>.onrender.com/health`

## Review

Done 2026-10-02. All local verification passed.

- Worked: unit tests 5/5 (DB stubbed); integration 1/1 vs Supabase; local uvicorn and Docker both return
  `/health` 200 and `/health/db` 200 `{"db":"ok","pgvector":"0.8.2"}`; container runs as non-root `app`.
- Also verified the failure path: with an unreachable DB the app still starts, `/health` stays 200 and
  `/health/db` returns 503 `{"db":"error","detail":"PoolTimeout"}` — full error only in logs.
- Changed vs plan: dev dep `httpx` → `httpx2` (Starlette deprecation warning); added Python ignores
  (`.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`) to `.gitignore` — not in the original file list.
- Friction: uv crashes inside the macOS sandbox (system-configuration proxy lookup), so uv/docker steps ran
  unsandboxed.
- Next: deploy to Render (Docker, root dir `api/`, health check path `/health`, env `DATABASE_URL`), then
  `curl https://<api>.onrender.com/health/db`. Add a linter/type-checker (ruff + pyright) to Commands.

---

# Task: ruff + pyright for lint and type-check

## Decisions (assumptions — confirm or change)

- Both as `api` dev dependencies (`uv add --dev ruff pyright`), config in `api/pyproject.toml`; no separate config files.
- ruff: line length 100; rules `E, F, W, I` (pyflakes/pycodestyle/isort) + `B` (bugbear) + `UP` (pyupgrade)
  + `ASYNC` (async pitfalls — relevant for the SSE/agent code) + `SIM`. Formatter: `ruff format`.
- pyright: `standard` mode (strict is too noisy for psycopg/FastAPI stubs at prototype speed), Python 3.12,
  uses `api/.venv`. Scope: `api/` (incl. tests).
- `scripts/check_db.py` is a standalone uv script with its own deps: ruff lints/formats it; pyright skips it.
- Fix whatever the first run reports; no rule ignores unless justified inline.

## Plan

- [x] `api/pyproject.toml` — dev deps + `[tool.ruff]` + `[tool.pyright]` (uv.lock updates automatically)
- [x] Run `ruff check --fix`, `ruff format`, `pyright`; fix remaining findings in code
- [x] `CLAUDE.md` Commands — replace "type-check / lint: not set up yet"
- [x] `README.md` Tests section — add the lint/type-check commands

## Verification

- [x] `uv run ruff check . ../scripts` and `uv run ruff format --check . ../scripts` clean (api + scripts)
- [x] `uv run pyright` — 0 errors
- [x] `uv run pytest` and `-m integration` still pass

## Review

Done 2026-10-02. ruff clean, format clean, pyright 0 errors; unit 5/5, integration 1/1, check_db.py OK.

- Findings fixed: 2 long lines (wrapped by `ruff format` in tests/test_health.py and scripts/check_db.py);
  1 pyright error — pydantic-settings `Settings()` gets `database_url` from env, invisible to pyright →
  one inline `pyright: ignore[reportCallIssue]` with the reason.
- Versions: ruff 0.16.10, pyright 1.1.414 (PyPI wrapper; downloads Node on first run).
- Next: a pre-commit hook or CI job running the same three commands so they can't drift.

---

# Task: GitHub Actions CI

## Decisions (approved)

- Workflow `.github/workflows/ci.yml`, on push to `main` and on pull requests; cancels superseded runs.
- Job `check` (always): `uv sync --locked`, ruff check, ruff format --check, pyright, unit tests.
- Job `integration`: `pytest -m integration` only when the `DATABASE_URL` repo secret is set
  (step-level guard; fork PRs get no secrets, so it skips there too).
- Job `docker`: build `api/Dockerfile` without pushing, so a broken image fails before Render deploys it.
- Least-privilege `permissions: contents: read`; actions pinned to current major versions.

## Plan

- [ ] `.github/workflows/ci.yml`
- [ ] Validate the YAML locally (actionlint if available), then push and watch the first run with `gh run watch`
- [ ] `README.md` — CI badge + note on the optional `DATABASE_URL` secret
- [ ] `CLAUDE.md` — map entry for `.github/workflows/ci.yml`

## Verification

- [ ] First CI run on GitHub: `check` and `docker` green; `integration` skipped (no secret yet)
