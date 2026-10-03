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

- [x] `.github/workflows/ci.yml`
- [x] Validate the YAML locally (actionlint if available), then push and watch the first run with `gh run watch`
- [x] `README.md` — CI badge + note on the optional `DATABASE_URL` secret
- [x] `CLAUDE.md` — map entry for `.github/workflows/ci.yml`

## Verification

- [x] First CI run on GitHub: `check` and `docker` green; `integration` skipped (no secret yet)

## Review

Done 2026-10-03. Run 37095897012 green: check ✅, docker ✅, integration ✅ (skip path; no secret yet).

- Worked: actionlint (via Docker) clean before pushing; step-level `env.DATABASE_URL` guard skips cleanly.
- Didn't: first run (596403e) failed at job setup: `astral-sh/setup-uv@v10` doesn't exist. setup-uv
  publishes only exact tags (v10.2.0), no moving major tag, and actionlint doesn't check that remote tags exist.
  Fixed in a763535 by pinning to the v10.2.0 commit SHA.
- Improve: check `git/ref/tags/<major>` for every action before pushing, or pin all actions by SHA
  (with a comment naming the version) and let Dependabot bump them.

---

# Task: deploy readiness (render.yaml + smoke endpoint) and kit quick fixes

## Decisions (assumptions — confirm or change)

- **Migrations:** plain numbered SQL files in `api/db/migrations/` + a ~40-line runner
  (`uv run python -m db.migrate`) that records applied files in `schema_migrations`. Reused live for
  documents/chunks/memory tables. Run from your machine: local and Render share one Supabase DB, and
  Render's pre-deploy command is paid-only.
- **Every table enables RLS** (no policies). Supabase exposes `public` tables through its REST API with
  the anon key; RLS blocks that, while our `postgres` connection (table owner) is unaffected.
- **`POST /smoke`:** in ONE transaction: insert a row with a vector → read it back → pgvector similarity
  query on the table → **roll back**. Proves write/read/vector permissions on a real table, leaves nothing
  behind, so the public endpoint can't be used to fill the DB. 503 on failure (error class only).
- **`render.yaml` (Blueprint):** one web service, Docker, `dockerfilePath: ./api/Dockerfile`,
  `dockerContext: ./api`, health check `/health`, region `virginia` (next to Supabase us-east-1),
  free plan, auto-deploy on `main` only when `api/**` changes, `DATABASE_URL` as `sync: false`
  (entered in the dashboard, never in git).
- **`scripts/smoke.sh [base_url]`:** curls `/health`, `/health/db`, `POST /smoke`; default localhost:8000.
  Same command for local, Docker and Render; prints elapsed time for the rehearsal log.
- **`.gitignore`:** stop ignoring all of `.claude/`; ignore the course's exact paths instead (36 skill
  dirs, 6 agents, references, hooks, examples, template files), generated from the course clone.
  `.agents/`, `.archon/`, `tooling/`, `.mcp.json` stay fully ignored. Add `.claude/settings.local.json`.
- **`.env.example`:** DATABASE_URL (required), ANTHROPIC_API_KEY, LANGFUSE_* , EMBEDDING_* placeholders;
  SUPABASE_URL/SUPABASE_KEY listed as optional (only needed for supabase-py/Storage).
- **`CLAUDE.md`:** add Ground rules (from what is already decided: uv/3.12, ruff+pyright clean, Pydantic I/O,
  config only via config.py, numbered SQL migrations, RLS on every table, secrets only in env),
  Working principles (from PREP_PLAN: review every diff, no untried libraries, narrow restarts),
  commit rule (every ~20 min, conventional prefix + rubric item), and a rubric map (item → where → status).

## Plan

- [x] `api/db/migrate.py` + `api/db/migrations/0001_smoke.sql`
- [x] `api/db/__init__.py` — `smoke_roundtrip()`; `api/main.py` — `POST /smoke`
- [x] `api/tests/test_health.py` — unit tests for `/smoke` (ok + 503), integration test against Supabase
- [x] `render.yaml`, `scripts/smoke.sh`
- [x] `.env.example`, `.gitignore`
- [x] `CLAUDE.md` (ground rules, working principles, commit rule, rubric map, map entries)
- [x] `README.md` — Deploy via Blueprint, migrations step, smoke script

## Verification

- [x] ruff, format, pyright clean; unit + integration tests pass
- [x] migrate runs against Supabase; re-run is a no-op; RLS enabled on `smoke_checks`
- [x] `scripts/smoke.sh` green locally and in Docker; table still empty afterwards
- [x] `git status` shows no course files after the .gitignore change
- [ ] (you) Render: New → Blueprint → set DATABASE_URL → `scripts/smoke.sh https://<api>.onrender.com`; time it, twice

## Review

Done 2026-10-03 (local). ruff/format/pyright clean; unit 9/9; integration 2/2; actionlint + shellcheck clean;
`scripts/smoke.sh` PASS locally and in Docker; `smoke_checks` has 0 rows afterwards; migrate re-run is a no-op.

- Worked: running the integration test *before* migrating confirmed the 503 `UndefinedTable` path against the
  real DB. Checked Render's Blueprint spec (autoDeployTrigger, buildFilter.paths) instead of writing it from
  memory, after the setup-uv@v10 miss.
- Found: Supabase already has `schema_migrations` in `auth` and `realtime`, so the runner now names
  `public.schema_migrations` explicitly. smoke.sh's first failure hint blamed migrations for an
  unreachable server; it now maps each failure ([000] / UndefinedTable / PoolTimeout) to its fix.
- .gitignore: 48 exact course paths instead of all of `.claude/`; own skills under `.claude/` are now tracked.
- Pending (you): push → Render New → Blueprint → DATABASE_URL → `scripts/smoke.sh <url>`; time it, twice.

---

# Task: /version route + CLAUDE.md deployment status

## Decisions

- `GET /version` → `{"commit": "<RENDER_GIT_COMMIT>"}`; `"local"` when unset (local/Docker). Read through
  `Settings.render_git_commit` (config only via get_settings). Public repo, so exposing the SHA is fine.
- `scripts/smoke.sh [base_url] [expected_sha]`: adds a `version` check; with an expected SHA (prefix ok)
  it FAILs on mismatch — `scripts/smoke.sh <url> "$(git rev-parse HEAD)"` proves the push is what's live.

## Plan

- [x] `api/config.py` field, `api/main.py` route, unit tests
- [x] `scripts/smoke.sh` version check + optional expected SHA
- [x] `CLAUDE.md`: Deployment row verified; Commands: clipboard command for DATABASE_URL, smoke with SHA
- [x] `README.md`: version row in the Verify table, SHA usage in Deploy

## Verification

- [x] ruff/format/pyright/shellcheck clean; tests pass
- [x] local: `/version` = local; smoke with wrong SHA fails, without SHA passes
- [x] after push: Render `/version` = pushed SHA via `scripts/smoke.sh <url> <sha>`

## Review

Done 2026-10-03. Pushed 52c6029 → CI green in 41 s → Render served 52c6029 at 82 s from push →
`scripts/smoke.sh https://fde-api.onrender.com 52c6029…` all PASS incl. `commit matches`.

- Worked: the version check removed the guesswork of the previous deploy (no screenshots needed);
  the wait loop polled /version until the pushed SHA appeared instead of sleeping a fixed time.
- Lesson from the 7e392b9 detour: I concluded auto-deploy had failed from a single deploy page; the
  Deploys list showed it had worked. Check the list (or /version) before diagnosing.
- Next: timed rehearsal 2 (delete + recreate Blueprint), then the PLAN.md template, pane prompts, eval template.

---

# Task: copy-db-url script + deploy runbook

Done 2026-10-03 (approved in chat; 2 new files + 2 link edits).

- [x] `scripts/copy-db-url.sh` — strips KEY=/quotes, adds sslmode, refuses placeholders/wrong scheme, masks output
- [x] `docs/runbook-deploy.md` — how it works, one-time setup, timed clean-slate deploy, everyday deploy,
      failure table, rollback, password rotation (no narration lines: public repo)
- [x] README Deploy + CLAUDE.md map/commands link both; old pbcopy one-liner removed

## Review

- Worked: tested the script against 7 fake .env cases with a stub pbcopy (user's clipboard untouched).
- Didn't: guessed Render rollback leaves auto-deploy on; docs say a dashboard rollback turns it off. Fixed.
- Rehearsal 2 log: copy step failed twice (table-mangled one-liner, clipboard overwritten by the next copy);
  the script replaces both.
