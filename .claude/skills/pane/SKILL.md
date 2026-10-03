---
name: pane
description: Run one parallel work pane through the PIV loop on one ticket — plan, stop for human review, implement, validate, commit — staying inside the pane's own folders. Use in each worktree after /piv-slice-epic has produced the tickets, e.g. "/pane B docs/tickets/<slug>.md#T2".
argument-hint: "<A|B|C|D> <ticket: path#id or the ticket text>"
---

# Pane $ARGUMENTS

You are one of four parallel panes. The first argument is your pane letter; the rest is your ticket.
Work the ticket through the PIV loop **with a human gate after planning**. Never use `piv-run-full-loop`:
the lead reviews every plan before code is written.

## Your folders

Edit only your pane's folders. Every other path is read-only for you.

| Pane | Owns | Typical rubric items |
|---|---|---|
| **A** backend + agents | `api/agents/` `api/schemas/` `api/guardrails/` `api/memory/` + the shared files below | Multi-agent orchestration · Framework · Guardrails · Memory |
| **B** retrieval + evals | `api/rag/` `api/db/migrations/` `evals/` | Embedding model · Vector DB · LLM Eval |
| **C** front end | `ui/` | Front end |
| **D** docs + deploy | `README.md` `docs/` `render.yaml` | GitHub · Deployment · the non-technical visual |

**Shared files are owned by pane A:** `api/main.py`, `api/config.py`, `api/pyproject.toml`, `api/uv.lock`,
`.env.example`, `CLAUDE.md`. If another pane needs a change there (a route, a setting, a dependency), it does
**not** edit them: it lists the exact change under "Needs from A" in its report. Two worktrees editing
`uv.lock` is a guaranteed merge conflict.

If the ticket can't be done without editing another pane's folder, stop and say so; don't work around it.

## Step 0 — Orient (1 min)

- Confirm you're in this pane's worktree: `git branch --show-current`.
- Read `CLAUDE.md` (map, ground rules) and your ticket. Read the PRD and architecture doc it links to only as
  far as the ticket needs.

## Step 1 — Plan

Run the `piv-plan-implementation` skill with the ticket. Constraints for this session:

- **Codebase only.** Skip the external research phase unless the ticket needs an API you haven't used; if so,
  read only that API's docs.
- **Time box: ~10 minutes.** A plan for one pane-sized ticket, not a design doc.
- **Scope = your folders.** The plan's file list may only contain your folders (plus "Needs from A" items).
- Name the plan `.claude/plans/<pane-letter>-<ticket-slug>.md`.

## Step 2 — STOP for review

Reply with a summary of at most 10 lines, then **wait for the lead to say go**:

- Files to create/modify (all inside your folders)
- Approach in 2–3 lines
- Risks or open questions
- The validation that will prove it works
- Needs from A (if any)

Don't write code before "go". If the lead asks for changes, update the plan and summarize again.

## Step 3 — Implement

Run the `piv-implement` skill with the plan file. Stay inside your folders.

## Step 4 — Validate

Run the `piv-validate` skill. If it fails, fix and re-run, at most twice; then report the failure instead of
looping.

## Step 5 — Commit

Run the `piv-commit` skill. The message names the rubric item: `<type>: <what> — <rubric item>`, e.g.
`feat: add critic agent — guardrails`. Commit whenever a plan task validates green, at least every ~20 minutes.
Don't push or merge; the lead merges the worktrees.

## Step 6 — Report (5 lines)

1. Done: what now works, in one sentence
2. Validation: PASS/FAIL per check
3. Files changed
4. Rubric item(s) covered
5. Needs from A / blockers / ready to merge
