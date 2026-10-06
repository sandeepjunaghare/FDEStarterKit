# CLAUDE.md — FDE Starter Kit

## What this is
RAG prototype with a four-agent pipeline (planner → retriever → answerer → critic) that answers with citations,
enforces guardrails in code, and keeps per-user session + persistent memory. Stack: Claude Agent SDK + FastAPI (SSE),
Supabase Postgres + pgvector, Streamlit front end, Langfuse evals, Docker → Render.

## Architecture map
<!-- Derived from research/tech-stack.md. BUILT: api/{main,config}.py, api/db/ (pool, smoke, migrations), api/tests/,
     Dockerfile, docker-compose.yml, render.yaml, scripts/, CI, evals/, ui/ skeleton. Everything else is the target layout — update as code lands. -->

Request flow: `ui` → `POST /chat` (SSE) → planner → retriever → answerer → critic → streamed answer with citations.

```
api/                      # FastAPI service — Render web service; streams responses over SSE
  main.py                 # app + lifespan (DB pool) + routes: GET /health (liveness, Render's check),
                          #   GET /version (deployed git commit), GET /health/db (Supabase + pgvector),
                          #   POST /smoke (write/read/vector roundtrip, rolled back), POST /chat (SSE, planned)
  agents/                 # Claude Agent SDK pipeline — one job per agent, no shared side effects
    planner.py            # router: in-scope → retrieve; out-of-scope → refuse
    retriever.py          # embed query → pgVector top-k from Supabase
    answerer.py           # draft answer that cites retrieved chunks
    critic.py             # guardrail gate before anything reaches the user — review this hardest
    pipeline.py           # wires the 4 agents and emits SSE events
  schemas/                # Pydantic I/O contracts for every agent — guardrails are enforced here, not in prompts
  guardrails/             # scope classifier, PII redaction, citation check, the one domain rule
  memory/                 # session memory (conversation) + persistent memory (user profile), scoped per user
  rag/                    # Voyage embedding client (EMBEDDING_MODEL/DIM; input_type document vs query) + ingestion
  db/                     # async psycopg pool (Supabase session pooler), check_db(), smoke_roundtrip()
    migrate.py            # applies migrations/*.sql once each, in name order: uv run python -m db.migrate
    migrations/           # numbered SQL files (0001_smoke.sql …) — the only way schema changes
  config.py               # all settings from env: .env locally, Render env vars in cloud
  tests/                  # pytest; DB stubbed by default, `-m integration` hits real Supabase
  pyproject.toml          # uv project (Python 3.12) + ruff/pyright/pytest config; uv.lock is committed
  Dockerfile              # Render builds this from GitHub (see render.yaml)
ui/                       # Streamlit app (own uv project) — calls the API via API_URL (default localhost:8710)
  app.py                  # skeleton: API/DB status; planned: chat view with citations + visible memory
  Dockerfile              # Streamlit on ${PORT:-8711}; .streamlit/config.toml holds port + demo settings
evals/                    # own uv project (pane B). Black-box eval of POST /ask: hit rate, citations, guardrails,
                          #   faithfulness (Claude judge) → terminal, results/, optional Langfuse. evals/README.md
  contract.py             # the /ask response shape pane A must implement, and the golden-set models
  golden/<scenario>.yaml  # 10–15 cases per scenario; example.yaml runs against the built-in fake pipeline
scripts/
  check_db.py             # standalone Supabase + pgvector check: uv run --script scripts/check_db.py
  smoke.sh                # deploy smoke test for any URL: scripts/smoke.sh [base_url] [latest|sha] [--wait]
  copy-db-url.sh          # copies DATABASE_URL from .env for a dashboard, password masked in output
  check_embeddings.py     # Voyage embedding check (dim = EMBEDDING_DIM, ranking): uv run --script scripts/check_embeddings.py
docs/runbook-deploy.md    # deploy procedure, troubleshooting, rollback, password rotation
docs/runbook-local.md     # fallback: run + demo api and ui locally (Docker or plain uv) when Render/CI is blocked
docs/runbook-kickoff.md   # brief → PRD → architecture → tickets → 4 worktree panes, minute by minute
docs/templates/           # discovery-raw.md: freeform capture during the call → /discovery sorts it into
                          #   discovery-notes.md (stakeholder questions mapped to PRD sections)
docs/visual/one-page.html # non-technical one-pager (pane D): edit the `page` object; flags jargon on screen
docs/<slug>.prd.md        # (per scenario) the what/why — /plan-create-prd
docs/architecture.md      # (per scenario) the how — /plan-architecture
docs/tickets/<slug>.md    # (per scenario) 4 parallel tickets, one per pane — /piv-slice-epic
.claude/skills/pane/      # /pane <A|B|C|D> <ticket>: PIV loop for one pane, stops for review after planning
.claude/skills/discovery/ # /discovery: raw call notes → docs/discovery-notes.md, never invents, lists the gaps
.claude/plans/ reports/   # plans and implementation reports written by the PIV skills (committed)
.worktreeinclude          # gitignored files /worktree-create copies into each worktree (.env, course skills)
.gitleaks.toml            # secret-scan rules (CI): defaults + Anthropic any-prefix, Voyage, Postgres URL with password
render.yaml               # Render Blueprint: Docker, virginia, /health, deploys after CI passes, DATABASE_URL set in dashboard
.github/workflows/ci.yml  # CI: ruff + pyright (api, evals, ui), unit tests (api, evals), gitleaks, Docker build, integration (only if DATABASE_URL secret set)
docker-compose.yml        # local run: api on 8710, ui on 8711 (the DB is Supabase cloud, not a container)
.env.example              # every env var the stack uses; copy to .env
research/tech-stack.md    # stack decisions + one-line defenses — the source for this map
```

External services (not in the repo): Supabase (Postgres + pgvector), Anthropic API, hosted embedding model, Langfuse, Render.

## How work flows
What before how: PRD → architecture → tickets (`docs/runbook-kickoff.md`), then each ticket runs the PIV loop in its
own worktree via `/pane`, which owns disjoint folders; shared files (`api/main.py`, `api/config.py`,
`api/pyproject.toml`, `api/uv.lock`, `.env.example`, `CLAUDE.md`) belong to pane A. Validate with `/piv-validate`.

## Rubric map

| Rubric item | Where | Status |
|---|---|---|
| Deployment | `render.yaml`, `api/Dockerfile`, `scripts/smoke.sh`, `docs/runbook-deploy.md` | verified: push → CI → auto-deploy (~35 s) → smoke OK; clean-slate deploy rehearsed in 1:29 |
| GitHub | `README.md`, `.github/workflows/ci.yml` | verified: CI green on the last 8 pushes (lint, types, unit tests, evals harness, ui lint + types, gitleaks, Docker build); README has the Handoff section |
| Vector DB | `api/db/`, `api/db/migrations/` | connection + smoke table built; documents/chunks table planned |
| Embedding model | `api/rag/`, `EMBEDDING_*` + `VOYAGE_API_KEY` in `.env` | chosen + verified: voyage-4, 1024 dims → `vector(1024)` (`scripts/check_embeddings.py`); rag/ client planned |
| Multi-agent orchestration | `api/agents/` | planned |
| Framework | `api/main.py` (FastAPI) | FastAPI built; Agent SDK planned |
| Memory | `api/memory/` | planned |
| Guardrails | `api/schemas/`, `api/guardrails/` | planned |
| LLM Eval | `evals/` | verified: harness tested (fake target); real Claude judge (claude-haiku-4-5) passes the example set (`evals/results/20261006-162139-example.json`) and flags an unsupported claim (`pytest -m integration`), Langfuse traces on; per-scenario golden set + `/ask` on the day |
| Front end | `ui/` | skeleton verified: Streamlit shows API + DB status, runs in Docker and with uv (`docs/runbook-local.md`); chat view planned |

## Ground rules
- **Python:** 3.12 via uv; add deps with `uv add` (never pip). `ruff check`, `ruff format --check` and `pyright` must be clean before a commit.
- **Types:** every agent input/output is a Pydantic model in `api/schemas/`; guardrails validate those models in code.
- **Config:** read settings only through `config.get_settings()`; never `os.environ` elsewhere. Secrets live in `.env` only; add new keys to `.env.example` **with empty values** (CI secret scan fails the build otherwise).
- **Database:** async psycopg pool from `app.state.pool`; SQL lives in `api/db/`. Schema changes only as a new numbered file in `api/db/migrations/`, never edits to an applied one. Every table runs `enable row level security` (no policies): Supabase's public REST API must not reach our tables.
- **Errors:** fail fast with specific exceptions; public responses name the error class only, full detail goes to logs.
- **Testing:** unit tests stub the DB and run offline; anything touching Supabase is `@pytest.mark.integration`.
- **Commits:** about every 20 minutes, conventional prefix plus the rubric item it serves, e.g. `feat: add critic agent — guardrails`.

## Working principles
- Review every diff before accepting it; never leave a parallel session running unattended for more than 10 minutes.
- No library that hasn't been used in a dry run. If a session stalls, restart it with a narrower prompt rather than debugging it by hand.
- Out-of-scope ideas go to a "Release 2" list, not into the code.
- If a deploy fails twice, run locally and say so.

## Commands
- install: `cd api && uv sync`
- test: `cd api && uv run pytest` (unit, no network) · `uv run pytest -m integration` (real Supabase)
- run: `cd api && uv run uvicorn main:app --reload --port 8710` · `cd ui && uv run streamlit run app.py` (port 8711) · both in Docker: `docker compose up --build` · fallback steps: `docs/runbook-local.md`
- migrate: `cd api && uv run python -m db.migrate` (local and Render share one Supabase DB, so run it once from here)
- smoke: `scripts/smoke.sh` (local) · `scripts/smoke.sh https://fde-api.onrender.com latest --wait` (Render; waits until the live api/ code matches HEAD)
- copy DATABASE_URL for a dashboard: `scripts/copy-db-url.sh` · full deploy procedure: `docs/runbook-deploy.md`
- DB check without the API: `uv run --script scripts/check_db.py` · embeddings: `uv run --script scripts/check_embeddings.py`
- secret scan: `docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.30.1 git /repo --config /repo/.gitleaks.toml --redact`
- lint + format: `cd api && uv run ruff check --fix . ../scripts && uv run ruff format . ../scripts`
- type-check: `cd api && uv run pyright` (standard mode; api/ only — scripts/ are standalone uv scripts)
- ui checks: `cd ui && uv run ruff check . && uv run ruff format --check . && uv run pyright` (ui/ is its own uv project)
- evals: `cd evals && uv run python run.py golden/<scenario>.yaml [--target URL|fake] [--only ids] [--compare results/x.json]` · checks: `cd evals && uv run ruff check . && uv run pyright && uv run pytest`
