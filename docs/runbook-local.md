# Runbook: run and demo locally

The fallback when the Render demo isn't available. Same code, same Supabase database, on your laptop:
API on **http://localhost:8710**, UI on **http://localhost:8711**. Rehearsed 2026-10-06 to `SMOKE OK`: Docker
~50 s cold (build 45 s), ~8 s warm; uv ~4 s.

Copy commands from the code blocks only. Run everything from the repo root unless a block says otherwise.

## When to switch

Switch as soon as one of these is true. Don't debug Render on camera.

- **CI is red** and there's no time to fix it. Render deploys only after CI passes (`checksPass`), so the
  latest code never reaches Render.
- A deploy **failed twice** (`CLAUDE.md` rule: run locally and say so).
- `scripts/smoke.sh https://fde-api.onrender.com latest --wait` fails, or hangs past 5 minutes.

## Route A: Docker (same images as Render)

```bash
docker compose up --build -d
scripts/smoke.sh --wait
```

`SMOKE OK` → open **http://localhost:8711**. The sidebar shows `http://api:8710` with three ✅ and the page says
"Connected to the API and the database". Logs: `docker compose logs -f api` (or `ui`).

If the build or a container fails, don't fix Docker: go to route B.

## Route B: plain uv (no Docker)

Two terminals. The API reads the repo-root `.env` (`DATABASE_URL`, keys); the UI needs no settings, it
defaults to the API on port 8710.

```bash
cd api && uv run uvicorn main:app --port 8710
```

```bash
cd ui && uv run streamlit run app.py
```

Third terminal, from the repo root:

```bash
scripts/smoke.sh --wait
```

`SMOKE OK` → open **http://localhost:8711**. The sidebar shows `http://localhost:8710` with three ✅. Stop with
Ctrl+C in each terminal.

## Show it working

```bash
cd evals && uv run python run.py golden/<scenario>.yaml
```

Evals default to the local API (`--target http://localhost:8710`). Then demo in the UI as the end user would.

**Say out loud:** "Render's pipeline is blocked, so I'm running the same code locally against the same cloud
database. `version` says `local`, and the smoke and evals are the same checks that gate the deploy."

## Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` / `address already in use` | Something else holds 8710/8711: `lsof -nP -iTCP:8710 -sTCP:LISTEN`, stop it, or use the other route |
| Smoke `503 UndefinedTable` | `cd api && uv run python -m db.migrate` |
| Smoke `503 PoolTimeout` | `DATABASE_URL` missing or wrong in `.env` |
| UI shows ❌ and `ConnectError` | API not running, or the UI points elsewhere: check the URL in the sidebar |
| UI stays on a grey skeleton | Hard-refresh the browser; Streamlit needs its websocket |

## Switch back to Render

Fix CI (or wait out Render), push, then:

```bash
scripts/smoke.sh https://fde-api.onrender.com latest --wait
docker compose down
```

## Before the day

- Docker Desktop running, then `docker compose build` once so route A starts warm.
- `cd api && uv sync` and `cd ui && uv sync` once so route B starts without downloads.
- Do one full run of route B. It's the one you'll reach for when everything else is failing.
