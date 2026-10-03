# CLAUDE.md — FDE Starter Kit

## What this is
RAG prototype with a four-agent pipeline (planner → retriever → answerer → critic) that answers with citations,
enforces guardrails in code, and keeps per-user session + persistent memory. Stack: Claude Agent SDK + FastAPI (SSE),
Supabase Postgres + pgvector, Streamlit front end, Langfuse evals, Docker → Render.

## Architecture map
<!-- Derived from research/tech-stack.md. BUILT: api/{main,config}.py, api/db/ (pool, smoke, migrations), api/tests/,
     Dockerfile, docker-compose.yml, render.yaml, scripts/, CI. Everything else is the target layout — update as code lands. -->

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
  rag/                    # embedding client (one hosted model; swap = one config line) + document ingestion
  db/                     # async psycopg pool (Supabase session pooler), check_db(), smoke_roundtrip()
    migrate.py            # applies migrations/*.sql once each, in name order: uv run python -m db.migrate
    migrations/           # numbered SQL files (0001_smoke.sql …) — the only way schema changes
  config.py               # all settings from env: .env locally, Render env vars in cloud
  tests/                  # pytest; DB stubbed by default, `-m integration` hits real Supabase
  pyproject.toml          # uv project (Python 3.12) + ruff/pyright/pytest config; uv.lock is committed
  Dockerfile              # Render builds this from GitHub (see render.yaml)
ui/                       # Streamlit app — second Render service; calls the API via API_URL
  app.py                  # chat view with citations + visible session/persistent memory
evals/                    # golden set (10–15 Q&A), retrieval hit rate, LLM-as-judge faithfulness → Langfuse
scripts/
  check_db.py             # standalone Supabase + pgvector check: uv run --script scripts/check_db.py
  smoke.sh                # deploy smoke test for any URL: scripts/smoke.sh [base_url] [expected_sha]
render.yaml               # Render Blueprint: Docker, virginia, /health, deploys after CI passes, DATABASE_URL set in dashboard
.github/workflows/ci.yml  # CI: ruff + pyright + unit tests, Docker build, integration (only if DATABASE_URL secret set)
docker-compose.yml        # local parity check: api now, ui when it exists (the DB is Supabase cloud, not a container)
.env.example              # every env var the stack uses; copy to .env
research/tech-stack.md    # stack decisions + one-line defenses — the source for this map
```

External services (not in the repo): Supabase (Postgres + pgvector), Anthropic API, hosted embedding model, Langfuse, Render.

## Rubric map

| Rubric item | Where | Status |
|---|---|---|
| Deployment | `render.yaml`, `api/Dockerfile`, `scripts/smoke.sh` | verified on Render: push → CI → auto-deploy (~35 s) → smoke OK; timed rehearsal 2 pending |
| GitHub | `README.md`, `.github/workflows/ci.yml` | built |
| Vector DB | `api/db/`, `api/db/migrations/` | connection + smoke table built; documents/chunks table planned |
| Embedding model | `api/rag/`, `EMBEDDING_*` in `.env` | planned; model not chosen (fixes vector size) |
| Multi-agent orchestration | `api/agents/` | planned |
| Framework | `api/main.py` (FastAPI) | FastAPI built; Agent SDK planned |
| Memory | `api/memory/` | planned |
| Guardrails | `api/schemas/`, `api/guardrails/` | planned |
| LLM Eval | `evals/` | planned |
| Front end | `ui/` | planned |

## Ground rules
- **Python:** 3.12 via uv; add deps with `uv add` (never pip). `ruff check`, `ruff format --check` and `pyright` must be clean before a commit.
- **Types:** every agent input/output is a Pydantic model in `api/schemas/`; guardrails validate those models in code.
- **Config:** read settings only through `config.get_settings()`; never `os.environ` elsewhere. Secrets live in env only; add new keys to `.env.example`.
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
- run: `cd api && uv run uvicorn main:app --reload` · in Docker: `docker compose up --build`
- migrate: `cd api && uv run python -m db.migrate` (local and Render share one Supabase DB, so run it once from here)
- smoke: `scripts/smoke.sh` (local) · `scripts/smoke.sh https://fde-api.onrender.com "$(git rev-parse HEAD)"` (Render; fails until the pushed commit is live)
- copy DATABASE_URL for a dashboard (no `KEY=`, no quotes, adds sslmode): `grep -m1 '^DATABASE_URL=' .env | cut -d= -f2- | tr -d "'\"" | sed '/sslmode=/!s/$/?sslmode=require/' | tr -d '\n' | pbcopy`
- DB check without the API: `uv run --script scripts/check_db.py`
- lint + format: `cd api && uv run ruff check --fix . ../scripts && uv run ruff format . ../scripts`
- type-check: `cd api && uv run pyright` (standard mode; api/ only — scripts/ are standalone uv scripts)
