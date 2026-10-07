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
- Found after pushing 4537cfa: `smoke.sh <url> "$(git rev-parse HEAD)"` (documented in 3 places) fails after any
  push that doesn't touch api/, because buildFilter skips the redeploy. And after a clean-slate Blueprint the
  live commit is HEAD, so "last api/ commit" isn't right either. Fix: `smoke.sh <url> latest` compares the
  live commit's api/ tree with HEAD's. Lesson: test documented commands against the state *after* the push.

---

# Task: smoke.sh --wait + deployment status (approved in chat)

Done 2026-10-03. Rehearsals: 2 = 8:01, 3 = 1:29 (copy-db-url + history-recalled wait loop).

- [x] `scripts/smoke.sh ... --wait`: polls until /health answers AND the expected code is live (old deploy
      stays healthy during a rebuild), gives up after SMOKE_WAIT_SECONDS (300). Tested 6 cases incl. timeout,
      server appearing mid-wait, flag in any position, unchanged behaviour without the flag.
- [x] Runbook timed steps reduced to 5 (wait replaces watch-log + copy-URL); README, CLAUDE.md updated;
      Deployment rubric row = verified, rehearsed 1:29.
- Note: first Write of smoke.sh was rejected (file changed since the tool last read it, because the previous
  edit went through python). Checked git diff (clean) before re-reading and overwriting.

---

# Task: align the kit with the course's stage 1 method (what → how → slices → PIV per pane)

Flow on the day (course defaults, decided in chat):
discovery with the architect → `/plan-create-prd` → `docs/<slug>.prd.md` (what/why) →
`/plan-architecture` → `docs/architecture.md` (how) → `/piv-slice-epic` → `docs/tickets/<slug>.md`
(4 parallel tickets) → `/worktree-create` (4 worktrees) → each pane runs the PIV loop on one ticket →
`/worktree-merge`. Deferred: stage 2/3, epic research (1.10), PR flow, `piv-run-full-loop`.

## Decisions (assumptions — confirm or change)

- **Course files stay local.** Edits to course skills (piv-validate) are gitignored and never published.
  Our own files (templates, runbook, `/pane` skill, `.worktreeinclude`) are committed.
- **Discovery template maps questions to PRD sections**, so the architect conversation *is* the PRD
  interview; its notes file is passed to `/plan-create-prd` as the reference doc.
- **`tech-stack.md` is passed to `/plan-architecture` as the reference doc**, so the session only decides
  scenario-specific choices (chunking + schema, domain guardrail rule, memory scope, golden eval set).
- **Slicing is steered to 4 tickets that own disjoint folders**, one per pane:
  A `api/agents/ api/schemas/ api/guardrails/ api/memory/` · B `api/rag/ api/db/migrations/ evals/` ·
  C `ui/` · D `README.md docs/ render.yaml` (+ visual). Disjoint folders keep `/worktree-merge` clean.
- **One own skill `/pane <A|B|C|D> <ticket>`** instead of four prompt files: one thing to remember; each
  pane's folder ownership lives in it. It runs the PIV steps with gates, never `piv-run-full-loop`:
  plan (`/piv-plan-implementation`, codebase-only, skip external research unless an API is unknown,
  time-box ~10 min) → **STOP for human review** → `/piv-implement` → `/piv-validate` → `/piv-commit`
  (message names the rubric item) → report.
- **`.worktreeinclude`** lists the gitignored files each worktree needs: `.env` + the course layer
  (`.claude/` course paths, `.agents/`, `.mcp.json`, `tooling/`). Without it, panes have no PIV skills.
  Add `worktrees/` to `.gitignore`.
- **Plans/reports are committed** (`.claude/plans/`, `.claude/reports/`): evidence of the process in the
  public repo. (Your call — flip to ignored if you prefer.)

## Plan

- [x] 1. `.claude/skills/piv-validate/SKILL.md` (local only): our 4 checks from `api/` — ruff check
      (`. ../scripts`), ruff format --check, pyright, pytest; integration tests optional (`-m integration`)
- [x] 2a. `docs/templates/discovery-notes.md`: discovery questions grouped by PRD section
      (problem/users/evidence · data · cost of a wrong answer · PII/regulatory · success metric · non-goals)
- [x] 2b. `docs/runbook-kickoff.md`: minute-by-minute kickoff with copy-ready commands (code blocks only):
      `/plan-create-prd`, `/plan-architecture`, `/piv-slice-epic` (4-folder instruction), `/worktree-create`,
      the four `/pane` launches, `/worktree-merge`; time boxes per step
- [x] 3. `.claude/skills/pane/SKILL.md` (own, committed): `/pane <letter> <ticket>` as above
- [x] 4. `.worktreeinclude` + `worktrees/` in `.gitignore`
- [x] 5. CLAUDE.md: map entries (docs/templates, runbook-kickoff, /pane, .worktreeinclude) + one line on the flow

## Verification

- [x] `piv-validate` run here: reports PASS with our real commands (and FAIL if a check is broken)
- [x] `/worktree-create` test branch: worktree has `.env` + course skills; `/pane` and `/piv-validate` resolve
      there; remove the test worktree afterwards
- [x] `git status`: no course files staged; own files tracked
- [ ] Dry run of the kickoff (not timed): fake scenario → PRD → architecture → tickets, to check the three
      skills accept the inputs and land files where the runbook says. Delete the generated docs after.

## Review

Done 2026-10-03, except the kickoff dry run (see below).

- piv-validate: our 4 checks; verified PASS on the clean tree and ❌ on lint/types/unit with a deliberately
  broken test file (moved out afterwards). Local only (gitignored), as intended.
- /worktree-create test-pane (the course skill itself): 125 ignored files copied via `.worktreeinclude`
  (.env, 36 course skills incl. customized piv-validate, .mcp.json, tooling); 0 tracked files duplicated;
  uv sync OK; lint/pyright/unit PASS; integration PASS inside the worktree (so .env works). Worktree and
  branch removed.
- Found while building: shared files (api/main.py, config.py, pyproject.toml, uv.lock, .env.example,
  CLAUDE.md) would conflict across worktrees → owned by pane A; other panes report "Needs from A".
- Found: docs must be committed before /worktree-create (worktrees branch from HEAD) → step in the runbook.
  Same reason /pane is absent from a worktree until it's committed.
- Not done: the kickoff dry run (PRD → architecture → tickets on a fake scenario). Those skills interview
  and gate on the user's answers, so it needs you at the keyboard; proposed as the first 40 minutes of Ex1.

---

# Task: eval harness template (design approved in chat)

## Decisions (approved)

- Black box over HTTP: `POST /ask` → `{answer, citations, refused, action, retrieved[{chunk_id, doc, text}]}`;
  `--target fake` = built-in fake pipeline for tests and before /ask exists. The /ask contract is pane A's
  interface note.
- `evals/` is its own uv project (never touches api/uv.lock). Command: `cd evals && uv run python run.py ...`
- Golden set YAML; expected sources = doc + snippet (robust to re-chunking).
- Metrics: hit rate @k, citation check, guardrail accuracy (deterministic) + faithfulness (Claude judge,
  default claude-haiku-4-5, structured output).
- `--only`, `--compare`, `--no-judge`; results to `evals/results/` (gitignored; demo run force-added);
  non-zero exit below thresholds. Langfuse optional, on when keys are set (verify SDK against current docs).

## Plan

- [x] `evals/pyproject.toml` (+ uv.lock): httpx, pydantic, pyyaml, anthropic, langfuse, python-dotenv; dev pytest/ruff/pyright
- [x] `evals/contract.py` (AskResponse, golden models), `golden.py`, `targets.py` (HTTP + fake), `metrics.py`,
      `judge.py`, `langfuse_sink.py`, `run.py` (CLI, table, results, compare, exit code)
- [x] `evals/golden/example.yaml` (4 cases: answerable ×2, out_of_scope, domain_rule) matching the fake corpus
- [x] `evals/tests/`: metrics unit tests, end-to-end run on fake target with stubbed judge, `--compare`;
      one `integration` test calling the real judge
- [x] `evals/README.md`: contract, golden format, commands
- [x] CI: evals job (ruff, format, pyright, pytest); `piv-validate` (local) gains the evals checks
- [x] `.gitignore` evals/results/; `.env.example` EVAL_JUDGE_MODEL; CLAUDE.md map/commands/rubric row; README Eval section

## Verification

- [x] evals: ruff/format/pyright clean, tests pass; CI green
- [x] `run.py golden/example.yaml --target fake` prints the table + summary; a deliberately failing case shows a reason
- [x] `--only`, `--compare` work; exit code non-zero below threshold
- [ ] real judge: one call with ANTHROPIC_API_KEY (if set in .env), otherwise reported as skipped
- [ ] Langfuse: push verified only if keys exist; otherwise reported as not verified

## Review

Built 2026-10-03. evals: ruff/format/pyright clean, 23 unit tests pass, `--target fake` → PASS; api untouched
(23 pass); CI gets an `evals` job (actionlint clean). CI run pending the push.

- Verified after keys were added: real judge (integration test flags the unsupported "24 hours" claim; full
  run scores both answered cases 1.00 with claude-haiku-4-5) and Langfuse (4 eval traces read back via the
  API with hit/citations/guardrails/faithfulness scores; scores lag a few seconds behind the trace).
- Near miss: the keys were first pasted into the tracked .env.example (uncommitted). Moved to .env without
  printing them; .env.example restored. → secret scan in CI (next task).
- Checked against docs instead of memory: anthropic 1.11 `messages.parse(output_format=Model)` →
  `parsed_output`; Langfuse SDK v4 (`get_client`, `start_as_current_observation`, `score_trace`) reads
  LANGFUSE_BASE_URL, so `.env.example`'s LANGFUSE_HOST was wrong and is fixed.
- Bugs the tests/real SDK caught: results path printed relative to the repo crashed for an outside dir; with
  no credentials the SDK raises TypeError at request time (not AuthenticationError) → crashed the run. Now a
  judge error with the fix in the message, and the run fails (exit 1) instead of looking green.
- Design change: /ask returns `action` only (no separate `refused` flag, which could contradict it).

---

# Task: Voyage embeddings + CI secret scan (approved in chat)

Done 2026-10-03.

- [x] Embedding model chosen and verified live: Voyage `voyage-4`, 1024 dims (→ `vector(1024)`), $0.06/1M,
      200M free; payment method added (lifts the no-card rate limits; free tokens still apply).
      `scripts/check_embeddings.py`: config → embed (document/query) → dimension → ranking. PASS, 59 tokens.
- [x] `.env.example`: EMBEDDING_MODEL=voyage-4, EMBEDDING_DIM=1024, VOYAGE_API_KEY= (empty); tech-stack row,
      CLAUDE.md (map, rubric row, commands, ground rule), README updated.
- [x] Secret scan: `.gitleaks.toml` + CI `secrets` job (gitleaks v8.30.1, full history).

## Review

- Tested the scanner both ways before trusting it. Gaps found against the real .env: the built-in Anthropic
  rule only knows `sk-ant-api03-…` (our key uses a newer prefix → missed); no Voyage rule; no Postgres-URL
  rule. Added all three; now all 4 real secrets are caught (Langfuse public key isn't a secret).
- First decoy test "passed" only because the decoy was malformed and `tail` masked the exit code; re-tested
  with correctly shaped fakes and the real exit code.
- False positive: the fake `s3cretPw` URL in api/tests → allowlisted that exact value, not the folder.
- Limit: CI catches a leak *after* the push. True prevention is a local pre-commit hook (not added).

---

# Task: README Handoff + non-technical visual template (approved in chat)

Done 2026-10-03.

- [x] README `## Handoff`: what you're getting, who owns what (golden set owned by the client's domain
      expert), changing it safely (eval before/after), what to watch first, known limits/Release 2,
      "if two engineers picked this up". Scenario fields as `<placeholders>` for pane D.
- [x] `docs/visual/one-page.html`: 16:9 one-pager, before/after, 3 numbers, trust + next; edit only the
      `page` object; on-screen red banner when jargon appears. Example content = fictional health plan.
- [x] CLAUDE.md map entry.

## Review

- Rendered with headless Chrome and looked at it: desktop 16:9 clean; jargon test ("vector database")
  shows the banner naming both words. Reworded the awkward third number card.
- Added rule: numbers not measured during the build are labelled as targets (example numbers are invented).
- Phone check: screenshot looked clipped, but measuring in-page showed headless Chrome's 500 px minimum
  layout width cropped to 390 px — no real overflow (doc width == viewport at 500/800). The minmax(0,1fr)
  change stays as a safeguard. A true 390 px check needs a real device or DevTools emulation.

---

# Task: raw discovery notes → /discovery skill fills the template (approved in chat)

Problem: filling `docs/templates/discovery-notes.md` live means navigating nested placeholders mid-conversation.
Fix: during the call, type freeform into a flat file. After the call (or mid-call, to find gaps), `/discovery`
sorts the notes into the template.

- [x] `docs/templates/discovery-raw.md`: tiny capture file. A 3-tag legend (`?` open question, `A:` assumption,
      `"` verbatim quote → Evidence), a one-line-per-section cheat sheet of the questions, then empty space.
      Untagged lines are fine.
- [x] `.claude/skills/discovery/SKILL.md`: `/discovery [raw file, default docs/discovery-raw.md]`
      - Reads the raw notes + the template; writes `docs/discovery-notes.md` in the template's exact structure
        (so `/plan-create-prd` input doesn't change).
      - Rules: keep the stakeholder's wording; never invent an answer; anything inferred rather than said is
        marked `ASSUMPTION`; `?` lines go to Open Questions; lines that fit nowhere go to an `Unsorted`
        section rather than being dropped.
      - Ends with a short gap list in chat (empty sections) so it can be run at ~minute 17 while the
        stakeholder is still in the room.
      - Asks before overwriting an existing `docs/discovery-notes.md`; leaves the raw file untouched.
- [x] `docs/runbook-kickoff.md` step 1: copy the raw template instead, type freely, run `/discovery`
      (optionally mid-call for gaps). Step 2 unchanged.
- [x] `docs/templates/discovery-notes.md` header: note that it's now usually generated by `/discovery`;
      still usable by hand.
- [x] `CLAUDE.md` map: add `docs/templates/discovery-raw.md` and the `/discovery` skill line.
- [x] Verify: write a realistic messy raw-notes sample in the scratchpad, run the skill's instructions on it,
      check every raw line lands somewhere, nothing is invented, and gaps are reported. Then commit
      (`docs: raw discovery capture + /discovery skill — GitHub`).

Done 2026-10-06. Raw file committed (user confirmed).

Assumptions: the raw file gets committed alongside `docs/discovery-notes.md` (same sensitivity). The sandbox
blocks shell writes to `.claude/skills/`, so the skill file is written with the Write tool (may prompt).

## Review

- Dry run by a fresh subagent on a messy 14-line sample (benefits helpdesk): every line placed, no invented
  facts, the one off-topic line went to Unsorted, `?`/`A:`/`"` tags routed correctly, WRONG condition flagged
  first in gaps. One inference marked ASSUMPTION (the "3 PDFs" = the plan docs), as the rules require.
- Not fixed (pre-existing): in the template, the bare `  -` placeholder lines make markdown render the line above
  as a setext heading. Generated notes don't have this (answers replace the bare dashes).
- Unverified: real timing mid-call (~minute 17 run). The dry run took ~35 s.

---

# Task: local fallback — UI skeleton + compose + uv route + runbook (approved in chat, option 1)

Done 2026-10-06.

Why: render.yaml deploys only when CI is green, so a red CI (or a Render problem) means the latest code can only
be demoed locally. Supabase outage is out of scope (user decision).

- [x] Local ports: API 8710, UI 8711 (8000/8501 are common and collide). Update compose, smoke.sh default,
      evals --target default, .env.example API_URL, README/evals README mentions. Render unaffected ($PORT).
- [x] `ui/` skeleton: pyproject (uv, 3.12, streamlit + httpx, ruff/pyright dev), app.py placeholder that calls
      /health, /version, /health/db and shows connected/error, Dockerfile (mirrors api/, port ${PORT:-8711}).
- [x] compose: api on 8710, ui on 8711 with API_URL=http://api:8710, ui depends on api.
- [x] Rehearse route A cold: `docker compose up --build -d` → smoke → UI shows connected; time it.
- [x] Rehearse route B: `uv run` api and ui in two terminals against Supabase cloud → smoke → UI connected.
- [x] `docs/runbook-local.md`: when to switch (CI red, deploy failed twice, Render smoke fails/hangs), route A,
      route B, smoke + evals on localhost, what to say, switch back, before-the-day warm build.
- [x] Links: runbook-deploy failure table, kickoff step 8, README, CLAUDE.md map/commands/rubric (Front end:
      skeleton built). Kickoff step 4 prompt: pane C owns ui/ + compose ui service, builds on the skeleton.
- [x] Lint/type-check ui, rehearse from the runbook text only, commit + push, smoke Render.

## Review

- Both routes rehearsed against Supabase cloud and checked in a real browser (agent-browser): Docker cold
  ~50 s / warm 8 s, uv ~4 s; UI shows "Connected to the API and the database" with three ✅.
- Headless Chrome `--screenshot` only caught Streamlit's loading skeleton (websocket render); agent-browser
  with a 6 s wait was needed. Noted in the runbook troubleshooting table.
- First smoke after `docker compose up -d` failed because the API wasn't up yet → runbook uses `--wait`.
- Moved Streamlit flags into ui/.streamlit/config.toml so Docker and uv behave the same; hid the
  "Deploy" toolbar button for demos.
- Port change touched smoke.sh, evals --target default, .env.example, READMEs. Render unaffected ($PORT).
- Not done: no CI job for ui/ (lint/types run locally only) and no Render service for ui (pane C/D on the day).

---

# Task: /chat vs /ask — one pipeline, two endpoints (approved in chat)

Why: CLAUDE.md, README and ui/ name `POST /chat` (SSE); evals/ and the kickoff checklist name `POST /ask` (JSON).
Neither exists yet. Decision: both, backed by the same pipeline; `/chat`'s final `done` event is an `AskResponse`.

Contract (to write once, in evals/README, and point to it from elsewhere):

- `POST /ask  {question, user_id}` → `AskResponse` JSON — evals, scripts, curl.
- `POST /chat {question, user_id}` → SSE: `status {agent}` · `token {text}` · `done AskResponse` — the UI.
- Same request body, same pipeline, same final model; `/chat` only adds progress + tokens.

Docs only; no code behaviour changes. evals/targets.py and its tests stay on `/ask`.

- [x] `evals/README.md` — "The `/ask` contract" → "The `/ask` and `/chat` contract": add the `/chat` SSE events
- [x] `evals/contract.py` — module docstring: one line that `/chat`'s `done` event carries the same `AskResponse`
- [x] `CLAUDE.md` — request flow line + `main.py` route list: `POST /ask` (JSON) and `POST /chat` (SSE), one pipeline
- [x] `README.md` — mermaid: label the evals → `POST /ask` path next to UI → `POST /chat (SSE)`
- [x] `docs/runbook-kickoff.md` step 3 checklist — `/ask` and `/chat` both return/end with `AskResponse`
- [x] `ui/app.py` — no change (placeholder already says `POST /chat`)

## Verification

- [x] `git grep -n -E "/chat|/ask"` — every hit consistent with the contract above
- [x] `cd evals && uv run ruff check . && uv run pyright && uv run pytest` (docstring touched)
- [x] markdownlint: no new errors on the touched .md files (3 old ones remain, see Review)

## Review

Done 2026-10-06. Docs + one docstring; no behaviour change.

- Worked: every `/chat` and `/ask` reference now says one pipeline, `/ask` = JSON, `/chat` = SSE ending in the
  same `AskResponse`. evals: ruff, format, pyright clean; pytest 23 passed.
- Changed vs plan: wrote the SSE so `token` events stream only the critic-approved answer. Streaming the answerer's
  draft would show unchecked text and break "critic is the gate before anything reaches the user".
- markdownlint: 3 errors left on untouched lines (README bare URL line 111 + `**Notes**` heading line 228,
  kickoff bare URL line 135); not fixed here.
