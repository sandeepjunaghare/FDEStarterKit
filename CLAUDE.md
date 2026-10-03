# CLAUDE.md — FDE Starter Kit

## What this is
RAG prototype with a four-agent pipeline (planner → retriever → answerer → critic) that answers with citations,
enforces guardrails in code, and keeps per-user session + persistent memory. Stack: Claude Agent SDK + FastAPI (SSE),
Supabase Postgres + pgvector, Streamlit front end, Langfuse evals, Docker → Render.

## Architecture map
<!-- Derived from research/tech-stack.md. BUILT: api/{main,config}.py, api/db/, api/tests/, Dockerfile,
     docker-compose.yml, scripts/check_db.py. Everything else is the target layout — update as code lands. -->

Request flow: `ui` → `POST /chat` (SSE) → planner → retriever → answerer → critic → streamed answer with citations.

```
api/                      # FastAPI service — Render web service #1; streams responses over SSE
  main.py                 # app + lifespan (DB pool) + routes: GET /health (liveness, Render's check),
                          #   GET /health/db (Supabase + pgvector, 503 on failure), POST /chat (SSE, planned)
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
  db/                     # async psycopg pool (Supabase session pooler) + check_db(); later pgvector queries, migrations
  config.py               # all settings from env: .env locally, Render env vars in cloud
  tests/                  # pytest; DB stubbed by default, `-m integration` hits real Supabase
  pyproject.toml          # uv project (Python 3.12); uv.lock is committed
  Dockerfile              # Render builds this from GitHub on push to main (root dir: api/)
ui/                       # Streamlit app — Render web service #2; calls the API via API_URL
  app.py                  # chat view with citations + visible session/persistent memory
  Dockerfile
evals/                    # golden set (10–15 Q&A), retrieval hit rate, LLM-as-judge faithfulness → Langfuse
scripts/
  check_db.py             # Supabase + pgvector smoke test (connect, extension, roundtrip): uv run --script scripts/check_db.py
.github/workflows/ci.yml  # CI: ruff + pyright + unit tests, Docker build, integration (only if DATABASE_URL secret set)
docker-compose.yml        # local parity check: api now, ui when it exists (the DB is Supabase cloud, not a container)
research/tech-stack.md    # stack decisions + one-line defenses — the source for this map
```

External services (not in the repo): Supabase (Postgres + pgvector), Anthropic API, hosted embedding model, Langfuse, Render.

## Commands
- install: `cd api && uv sync`
- test: `cd api && uv run pytest` (unit, no network) · `uv run pytest -m integration` (real Supabase)
- run: `cd api && uv run uvicorn main:app --reload` · in Docker: `docker compose up --build`
- DB smoke test: `uv run --script scripts/check_db.py`
- lint + format: `cd api && uv run ruff check --fix . ../scripts && uv run ruff format . ../scripts`
- type-check: `cd api && uv run pyright` (standard mode; api/ only — scripts/ are standalone uv scripts)
