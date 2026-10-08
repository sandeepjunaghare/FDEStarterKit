# Runbook: kickoff, from brief to four parallel panes

The method: a clean **what** (PRD) and **how** (architecture), sliced into tickets, before any code. Then one
ticket per pane through the PIV loop (Plan → Implement → Validate), in parallel git worktrees.

```
brief → discovery notes → /plan-create-prd → /plan-architecture → /piv-slice-epic → commit
      → /worktree-create ×4 → /pane A|B|C|D (plan → review → implement → validate → commit) → /worktree-merge
```

Copy commands from the code blocks only. Replace `<slug>` with the PRD's file slug once it exists.

| Time (h:mm) | Step | Output |
|---|---|---|
| 0:00–0:10 | Read the brief, pick the scenario | — |
| 0:10–0:20 | 1. Discovery | `docs/discovery-notes.md` |
| 0:20–0:27 | 2. PRD (what / why) | `docs/<slug>.prd.md` |
| 0:27–0:34 | 3. Architecture (how) | `docs/architecture.md` |
| 0:34–0:38 | 4. Tickets + commit | `docs/tickets/<slug>.md` |
| 0:38–0:42 | 5. Worktrees + launch panes | `worktrees/pane-{a,b,c,d}` |
| 0:42–1:40 | 6. Panes: plan → **review** → build | commits per pane |
| 1:40–1:50 | 7. Merge + validate + local end-to-end check | app working on localhost |
| 1:50–2:05 | 8. Deploy + evals live | `docs/runbook-deploy.md` |

Time boxes are targets. If a step runs over, tighten its input; don't skip the step.

---

## 0. Before the day: a fresh Supabase project

The practice database holds other exercises' tables (`chunks`, `filings`, `session_turns`, `user_profiles`) and
migrations (`0002_filings_chunks.sql`, `0003_memory.sql`). A day-of `0002_*` would be skipped if its name matched
an old one, or a `create table if not exists chunks` would quietly reuse the old 131-row table and retrieval would
return another scenario's text. So the day runs on a new, empty project:

1. Supabase → New project (region us-east-1, next to Render's virginia) → Database → Extensions → `vector`.
2. Connect → Session pooler URL → `DATABASE_URL` in `.env` and in Render → fde-api → Environment.
3. `uv run --script scripts/check_db.py` → `cd api && uv run python -m db.migrate` (only `0001_smoke.sql`).
4. `scripts/smoke.sh` locally, then `scripts/smoke.sh https://fde-api.onrender.com latest --wait`.
5. Render → Environment also has `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` (declared in `render.yaml`).

---

## 1. Discovery (0:10–0:20)

```bash
cp docs/templates/discovery-raw.md docs/discovery-raw.md
```

Paste the brief after `Brief:`. Ask 5–6 questions from the cheat sheet and type answers in any order under
`Notes:` (tags optional: `?` open question, `A:` assumption, `"` quote). Around 0:17, and again at the end:

```
/discovery
```

It sorts the notes into `docs/discovery-notes.md` without inventing anything and lists the empty sections, so
you can ask about them while the stakeholder is still there.

## 2. PRD: the what (0:20–0:27)

```
/plan-create-prd <one-line idea from the brief> · docs/discovery-notes.md
```

The notes answer most of its interview; it asks only about gaps. Insist on the hypothesis's WRONG condition.
Output: `docs/<slug>.prd.md`.

## 3. Architecture: the how (0:27–0:34)

```
/plan-architecture docs/<slug>.prd.md · research/tech-stack.md CLAUDE.md
```

The stack is already decided in `research/tech-stack.md`; tell it to treat those as fixed and decide only the
scenario-specific parts: chunking + table schema, the domain guardrail rule, memory scope, the golden eval set.
Output: a standalone `docs/architecture.md`.

Before moving on, check that it has a **Data model + domain rule** section with all of these. Panes A and B
build straight from it, so a vague line here becomes a guess in two panes:

- [ ] **Chunks table:** columns and types, `embedding vector(1024)`, `enable row level security`. Becomes
      `api/db/migrations/0002_*.sql` (pane B).
- [ ] **Chunking:** unit (section, page, row) and size; what `doc` and `chunk_id` hold. `chunk_id` must be
      stable, since citations and the golden set point at it.
- [ ] **`/ask` and `/chat` response:** `/ask` returns `evals/contract.py` `AskResponse` (answer, citations,
      action, retrieved); `/chat` streams the same pipeline and ends with that `AskResponse` as its `done` event
      (`evals/README.md`). Which `action` values this scenario uses: answer, refuse, redact, escalate.
- [ ] **Domain rule:** one testable sentence, "refuse/escalate if …; every answer must cite …", plus what the
      user sees when it fires. Lives in `api/guardrails/` (pane A).
- [ ] **Golden cases for it:** at least one `domain_rule` case, one `out_of_scope`, one `pii` (pane B,
      `evals/golden/<scenario>.yaml`).
- [ ] **Memory scope:** what's kept per session vs per user profile, keyed by `user_id`.

## 4. Tickets (0:34–0:38)

```
/piv-slice-epic docs/<slug>.prd.md docs/architecture.md · local tracker: docs/tickets/<slug>.md · Slice into exactly 4 tickets that run in parallel, one per pane, each owning disjoint folders: A = api/agents api/schemas api/guardrails api/memory + shared files (api/main.py api/config.py api/pyproject.toml .env.example CLAUDE.md); B = api/rag api/db/migrations evals; C = ui + the ui service in docker-compose.yml (build on the existing skeleton: keep ui/Dockerfile and .streamlit/config.toml); D = README.md docs render.yaml + non-technical visual. Name them T1–T4 for panes A–D. Cross-pane needs go to pane A as explicit interface notes.
```

Commit before branching, or the worktrees won't have the docs:

```bash
git add docs/ && git commit -m "docs: PRD, architecture and tickets — planning" && git push
```

## 5. Worktrees + panes (0:38–0:42)

```
/worktree-create pane-a pane-b pane-c pane-d
```

It copies `.env` and the course skills into each worktree (`.worktreeinclude`). Then one terminal per pane:

```bash
cd worktrees/pane-a && claude
```

```
/pane A docs/tickets/<slug>.md#T1
```

Repeat for `pane-b` (`/pane B …#T2`), `pane-c` (`/pane C …#T3`), `pane-d` (`/pane D …#T4`).

## 6. Build (0:42–1:40)

Each pane plans, then **stops for your review** (≤10-line summary). Review the plan, say `go` or ask for changes.
Rotate through the panes; don't leave one unattended for more than 10 minutes. Each pane validates and commits
on its own branch, with the rubric item in the message. "Needs from A" items go to pane A.
Panes A and B: start from the patterns in **Dry-run lessons** at the end of this runbook.

## 7. Merge + validate (1:40–1:50)

```
/worktree-merge pane-a pane-b pane-c pane-d
```

Then run `/piv-validate` on the merged result. **Don't push yet.**

**Local end-to-end check (~3 min), the gate before deploy.** As soon as everything is merged, show the whole app
working on the laptop with plain uv (same Supabase database as Render):

Three terminals, each starting at the repo root (migrate is a no-op when nothing is new):

```bash
cd api && uv run python -m db.migrate && uv run uvicorn main:app --port 8710   # terminal 1
cd ui && uv run streamlit run app.py                                          # terminal 2
scripts/smoke.sh --wait                                                       # terminal 3
```

Open <http://localhost:8711> and ask 2–3 golden questions: one answered with citations, one the domain rule
refuses. Works → step 8. Doesn't → fix on `main` and re-check; don't push a broken app to find out on Render.

## 8. Deploy (1:50–2:05)

```bash
git push
scripts/smoke.sh https://fde-api.onrender.com latest --wait
```

Migrations already ran in step 7 (local and Render share one database). Full procedure:
`docs/runbook-deploy.md`. Render failing or CI red with no time to fix: `docs/runbook-local.md`.

---

## Dry-run lessons (2026-10-07)

A throwaway `/ask` (4 agents, Messages API, Voyage → pgvector) was built on the fake benefits corpus, run
against `evals/golden/example.yaml` (PASS, every metric 1.00), then deleted. What carries over to the day:

**Patterns that worked (pane A/B, copy them):**

- **One shared LLM helper** (`agents/llm.py`): `client.beta.messages.parse(model, system, messages,
  output_format=<Pydantic model>)`, the same call `evals/judge.py` makes. It maps `stop_reason == "refusal"` →
  `action=refuse`, `parsed_output is None` → error, and API/connection errors → one specific exception class.
  `/ask` returns 503 with the class name only.
- **Models:** `claude-haiku-4-5` for planner and critic; `claude-sonnet-5-5` for the answerer with
  `output_config={"effort": "low"}` plus `betas=["server-side-fallback-2026-07-01"], fallbacks="default"`.
- **Critic:** deterministic citation check first (non-empty, ⊆ retrieved chunk ids), then the LLM check.
- **Ingest:** stable `chunk_id = "<doc stem>-<ord>"`, `insert … on conflict (chunk_id) do update`, so
  re-running it never duplicates chunks. `input_type="document"` at ingest, `"query"` at search.
- **Search:** `1 - (embedding <=> %s::vector)` as score, `order by embedding <=> %s::vector limit k`, with an
  HNSW `vector_cosine_ops` index.
- **Settings:** `anthropic_api_key`, `voyage_api_key`, `embedding_model`, `embedding_dim` in `config.py` with
  empty defaults (the health routes still start without them); the clients take the key from settings, because
  `.env` is read by pydantic-settings and never lands in `os.environ`.

**Numbers to plan around:**

- Answerable question: **6.5–8 s** (planner 1–2.6 · retriever 0.3–0.4 · answerer 2–3.3 · critic 1.6–2.7 s).
  Refusal: 1–2 s (stops at the planner). The `/chat` status events matter, and the UI's HTTP timeout must be
  ≥ 30 s (the skeleton uses 10 s).
- Ingest of 7 chunks: ~1 s embed. 4-case eval run: 10 s.

**Friction (lost minutes in the dry run):**

- The Claude Code sandbox blocks uv's cache: `uv add` / `uv run` need the sandbox off.
- Ruff's line limit is 100: wrap long prompt lines in the system prompts.
- Pyright: `from voyageai.client_async import AsyncClient` (not `voyageai.AsyncClient`).
