# Runbook: kickoff, from brief to four parallel panes

The method: a clean **what** (PRD) and **how** (architecture), sliced into tickets, before any code. Then one
ticket per pane through the PIV loop (Plan → Implement → Validate), in parallel git worktrees.

```
brief → discovery notes → /plan-create-prd → /plan-architecture → /piv-slice-epic → commit
      → /worktree-create ×4 → /pane A|B|C|D (plan → review → implement → validate → commit) → /worktree-merge
```

Copy commands from the code blocks only. Replace `<slug>` with the PRD's file slug once it exists.

| Minute | Step | Output |
|---|---|---|
| 0–10 | Read the brief, pick the scenario | — |
| 10–20 | 1. Discovery | `docs/discovery-notes.md` |
| 20–27 | 2. PRD (what / why) | `docs/<slug>.prd.md` |
| 27–34 | 3. Architecture (how) | `docs/architecture.md` |
| 34–38 | 4. Tickets + commit | `docs/tickets/<slug>.md` |
| 38–42 | 5. Worktrees + launch panes | `worktrees/pane-{a,b,c,d}` |
| 42–100 | 6. Panes: plan → **review** → build | commits per pane |
| 100–110 | 7. Merge + validate | one branch on `main` |
| 110–125 | 8. Deploy + evals live | `docs/runbook-deploy.md` |

Time boxes are targets. If a step runs over, tighten its input; don't skip the step.

---

## 1. Discovery (minutes 10–20)

```bash
cp docs/templates/discovery-raw.md docs/discovery-raw.md
```

Paste the brief after `Brief:`. Ask 5–6 questions from the cheat sheet and type answers in any order under
`Notes:` (tags optional: `?` open question, `A:` assumption, `"` quote). Around minute 17, and again at the end:

```
/discovery
```

It sorts the notes into `docs/discovery-notes.md` without inventing anything and lists the empty sections, so
you can ask about them while the stakeholder is still there.

## 2. PRD: the what (minutes 20–27)

```
/plan-create-prd <one-line idea from the brief> · docs/discovery-notes.md
```

The notes answer most of its interview; it asks only about gaps. Insist on the hypothesis's WRONG condition.
Output: `docs/<slug>.prd.md`.

## 3. Architecture: the how (minutes 27–34)

```
/plan-architecture docs/<slug>.prd.md · research/tech-stack.md CLAUDE.md
```

The stack is already decided in `research/tech-stack.md`; tell it to treat those as fixed and decide only the
scenario-specific parts: chunking + table schema, the domain guardrail rule, memory scope, the golden eval set.
Output: a standalone `docs/architecture.md`.

## 4. Tickets (minutes 34–38)

```
/piv-slice-epic docs/<slug>.prd.md docs/architecture.md · local tracker: docs/tickets/<slug>.md · Slice into exactly 4 tickets that run in parallel, one per pane, each owning disjoint folders: A = api/agents api/schemas api/guardrails api/memory + shared files (api/main.py api/config.py api/pyproject.toml .env.example CLAUDE.md); B = api/rag api/db/migrations evals; C = ui; D = README.md docs render.yaml + non-technical visual. Name them T1–T4 for panes A–D. Cross-pane needs go to pane A as explicit interface notes.
```

Commit before branching, or the worktrees won't have the docs:

```bash
git add docs/ && git commit -m "docs: PRD, architecture and tickets — planning" && git push
```

## 5. Worktrees + panes (minutes 38–42)

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

## 6. Build (minutes 42–100)

Each pane plans, then **stops for your review** (≤10-line summary). Review the plan, say `go` or ask for changes.
Rotate through the panes; don't leave one unattended for more than 10 minutes. Each pane validates and commits
on its own branch, with the rubric item in the message. "Needs from A" items go to pane A.

## 7. Merge + validate (minutes 100–110)

```
/worktree-merge pane-a pane-b pane-c pane-d
```

Then run `/piv-validate` on the merged result and push.

## 8. Deploy (minutes 110–125)

```bash
git push
scripts/smoke.sh https://fde-api.onrender.com latest --wait
```

New migrations from pane B: `cd api && uv run python -m db.migrate` before the smoke test. Full procedure:
`docs/runbook-deploy.md`.
