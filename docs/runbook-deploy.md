# Runbook: deploy the API to Render

How `fde-api` gets from this repo to a public URL, how to prove the right code is live, and what to do when it isn't. Every command runs from the repo root. Copy commands from the code blocks only.

**Target:** clean slate to `SMOKE OK` in under 5 minutes. Render build plus deploy takes about 35 seconds; the rest is the dashboard.

---

## How it works

```
git push → GitHub CI (lint, types, tests, Docker build) → Render auto-deploys after checks pass → /version shows the new commit
```

- The service is defined in [`render.yaml`](../render.yaml) (a Render Blueprint): Docker, free plan, region `virginia` (next to Supabase us-east-1), health check `/health`, auto-deploy after CI passes, only when `api/**` changes.
- The only secret is `DATABASE_URL`, entered in the Render dashboard. It is never in git.
- The database is Supabase, shared by local runs and Render. Migrations run from your machine.

---

## One-time setup

These are done once per account or database, not per deploy.

1. **Render can see the repo.** Render → New → Blueprint → **Configure account** (GitHub) → Repository access → add `FDEStarterKit` → Save.
2. **Database schema is current.** Needed for a new Supabase project, or after adding a migration:

   ```bash
   cd api && uv run python -m db.migrate && cd ..
   ```

   Re-running is safe: already-applied files are skipped.

---

## Deploy from a clean slate (timed)

### Pre-flight (untimed)

Local `main` must match GitHub, because Render builds what's on GitHub:

```bash
git fetch -q && git status -sb | head -1
```

Expect `## main...origin/main` with no `[ahead …]` or `[behind …]`.

### Teardown (rehearsals only, untimed)

1. Render → Blueprints → the Blueprint → **Settings → Disconnect Blueprint**. This unlinks it; the service keeps running.
2. Render → **fde-api → Settings → Delete Web Service** → type the name to confirm.
3. The dashboard shows no `fde-api` and no Blueprint.

### Steps (start the timer)

**1. Copy the database URL.** Do this last before switching to Render. Copying anything else afterwards replaces it.

```bash
scripts/copy-db-url.sh
```

It prints the URL with the password masked. It must start with `postgresql://postgres.<your-project-ref>:***@…pooler.supabase.com:5432/postgres?sslmode=require`.

**2. Create the Blueprint.** Render → **New → Blueprint** → select `sandeepjunaghare/FDEStarterKit` → name it (e.g. `fde-starter-kit`).

**3. Paste `DATABASE_URL`.** Cmd+V into the `DATABASE_URL` field. It should start with `postgresql://` and contain no `DATABASE_URL=`, quotes or `<placeholders>`.

**4. Deploy.** Click **Deploy Blueprint** → open **fde-api** → wait for **Live**.

**5. Copy the service URL** from the top of the fde-api page. Usually `https://fde-api.onrender.com`; Render adds a suffix if the name is taken.

**6. Smoke test, checking the live API code matches `main`:**

```bash
URL=https://fde-api.onrender.com
scripts/smoke.sh "$URL" latest
```

**7. Stop the timer at `SMOKE OK`.**

```
PASS  health     {"status":"ok"}
PASS  version    {"commit":"<sha>"}
PASS  commit     live <sha7> has the same api/ code as HEAD <sha7>
PASS  health/db  {"db":"ok","pgvector":"0.8.2"}
PASS  smoke      {"smoke":"ok","write":"ok","read":"ok","vector_search":"ok","distance":0.0}
SMOKE OK
```

---

## Everyday deploy

After the one-time setup, deploying is a push:

```bash
git push
scripts/smoke.sh https://fde-api.onrender.com latest
```

`latest` passes when the live commit has the same `api/` code as your `HEAD`. After an `api/` change it fails with `different api/ code` until the new deploy is live (about 40 s after CI passes, roughly 80 s after the push); re-run it until it passes.

Changes outside `api/` (docs, scripts) do not redeploy, by design (`buildFilter` in `render.yaml`). The live commit is then older than `HEAD`, which `latest` accepts because the API code is identical. To require one exact commit instead, pass its SHA: `scripts/smoke.sh <url> 52c6029`.

---

## When something fails

| Symptom | Cause | Fix |
|---|---|---|
| Deploy log: `validation error for Settings … DATABASE_URL` | Malformed value: `KEY=` prefix, quotes, placeholder or wrong scheme. The message says which | Render → fde-api → **Environment** → fix → **Save, rebuild, and deploy**. Use `scripts/copy-db-url.sh` |
| Smoke `[000] curl failed` | Still deploying, or a free instance waking up (up to ~60 s) | Wait 30 s, re-run step 6 |
| Smoke `commit … different api/ code than HEAD` | New deploy not live yet, or Render built an older commit | Wait a minute. Still old: check the pre-flight, then **Manual Deploy → Deploy latest commit** |
| Smoke `commit … unknown locally` | Live commit isn't in your clone | `git fetch` and re-run |
| `503 {"detail":"PoolTimeout"}` | Render can't log in to Supabase | Render → fde-api → **Logs**, search `error connecting`. `tenant/user … not found`: wrong project ref or placeholder in the URL. `invalid connection option`: `KEY=` pasted into the value |
| `503 {"detail":"UndefinedTable"}` | Migrations not applied to this database | `cd api && uv run python -m db.migrate` |
| Repo missing in Render's picker | Render's GitHub app lacks access | One-time setup, step 1 |
| Push didn't deploy | CI failed, change was outside `api/`, or auto-deploy is off | GitHub → Actions for CI. Render → fde-api → **Settings → Build & Deploy → Auto-Deploy** = After CI Checks Pass |

---

## Roll back

- **Fastest:** Render → fde-api → **Deploys** → a previous successful deploy → **Rollback**. A dashboard rollback **turns auto-deploy off**, so pushes stop deploying. Once `main` is fixed, set **Settings → Build & Deploy → Auto-Deploy** back to After CI Checks Pass.
- **Durable:** revert in git, so `main` and the live service agree:

  ```bash
  git revert <bad-sha> && git push
  ```

---

## Rotate the database password

1. Supabase → Project Settings → Database → **Reset database password**.
2. Update `DATABASE_URL` in `.env`.
3. `scripts/copy-db-url.sh` → Render → fde-api → **Environment** → paste → **Save, rebuild, and deploy**.
4. `scripts/smoke.sh https://fde-api.onrender.com` and, if set, update the GitHub Actions secret `DATABASE_URL`.

---

## Notes

- **Free plan:** the instance sleeps after inactivity. Open `/health` a minute before a demo.
- **`/health` never touches the database,** so a Supabase blip can't fail a deploy. `/health/db` and `POST /smoke` check the data path.
- **`POST /smoke` leaves nothing behind:** it writes, reads and vector-searches a row in one transaction that is rolled back.
