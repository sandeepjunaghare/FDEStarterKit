#!/usr/bin/env bash
# Deploy smoke test: liveness, deployed commit, DB + pgvector, and a write/read/vector-search
# roundtrip (rolled back).
# Usage: scripts/smoke.sh [base_url] [expected_sha]   (default http://localhost:8000)
#   scripts/smoke.sh https://fde-api.onrender.com "$(git rev-parse HEAD)"   # FAILs if another commit is live
set -euo pipefail

base="${1:-http://localhost:8000}"
base="${base%/}"
expected="${2:-}"
start=$SECONDS
fail=0

last_body=""

check() {
  local label=$1 method=$2 path=$3 body code
  # 90 s timeout: a sleeping Render free instance takes 30–60 s to wake.
  body=$(curl -sS -X "$method" --max-time 90 -w $'\n%{http_code}' "$base$path") || body=$'curl failed\n000'
  code=${body##*$'\n'}
  body=${body%$'\n'*}
  last_body=$body
  if [[ $code == 200 ]]; then
    printf 'PASS  %-10s %s\n' "$label" "$body"
  else
    printf 'FAIL  %-10s [%s] %s\n' "$label" "$code" "$body"
    fail=1
  fi
}

echo "target: $base"
check health GET /health
check version GET /version
commit=$(sed -n 's/.*"commit":"\([^"]*\)".*/\1/p' <<<"$last_body")
if [[ -n $expected ]]; then
  # Prefix match either way, so short and full SHAs compare equal.
  if [[ -n $commit && ($commit == "$expected"* || $expected == "$commit"*) ]]; then
    printf 'PASS  %-10s live commit matches %s\n' "commit" "${expected:0:7}"
  else
    printf 'FAIL  %-10s live is %s, expected %s\n' "commit" "${commit:-unknown}" "${expected:0:7}"
    fail=1
  fi
fi
check health/db GET /health/db
check smoke POST /smoke
echo "elapsed: $((SECONDS - start))s"

if ((fail)); then
  echo "SMOKE FAILED"
  echo "  [000]                 -> server unreachable, or still waking/deploying: retry or check Render logs"
  echo "  503 UndefinedTable    -> migrations not applied: cd api && uv run python -m db.migrate"
  echo "  503 PoolTimeout/other -> DATABASE_URL wrong or missing in this environment"
  echo "  commit mismatch       -> new deploy not live yet (CI or build still running): retry in a minute"
  exit 1
fi
echo "SMOKE OK"
