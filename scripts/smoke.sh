#!/usr/bin/env bash
# Deploy smoke test: liveness, DB + pgvector, and a write/read/vector-search roundtrip (rolled back).
# Usage: scripts/smoke.sh [base_url]   (default http://localhost:8000)
#   scripts/smoke.sh https://fde-api.onrender.com
set -euo pipefail

base="${1:-http://localhost:8000}"
base="${base%/}"
start=$SECONDS
fail=0

check() {
  local label=$1 method=$2 path=$3 body code
  # 90 s timeout: a sleeping Render free instance takes 30–60 s to wake.
  body=$(curl -sS -X "$method" --max-time 90 -w $'\n%{http_code}' "$base$path") || body=$'curl failed\n000'
  code=${body##*$'\n'}
  body=${body%$'\n'*}
  if [[ $code == 200 ]]; then
    printf 'PASS  %-10s %s\n' "$label" "$body"
  else
    printf 'FAIL  %-10s [%s] %s\n' "$label" "$code" "$body"
    fail=1
  fi
}

echo "target: $base"
check health GET /health
check health/db GET /health/db
check smoke POST /smoke
echo "elapsed: $((SECONDS - start))s"

if ((fail)); then
  echo "SMOKE FAILED"
  echo "  [000]                 -> server unreachable, or still waking/deploying: retry or check Render logs"
  echo "  503 UndefinedTable    -> migrations not applied: cd api && uv run python -m db.migrate"
  echo "  503 PoolTimeout/other -> DATABASE_URL wrong or missing in this environment"
  exit 1
fi
echo "SMOKE OK"
