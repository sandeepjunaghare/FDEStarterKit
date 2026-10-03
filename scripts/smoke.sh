#!/usr/bin/env bash
# Deploy smoke test: liveness, deployed commit, DB + pgvector, and a write/read/vector-search
# roundtrip (rolled back).
# Usage: scripts/smoke.sh [base_url] [latest|expected_sha]   (default http://localhost:8000)
#   scripts/smoke.sh https://fde-api.onrender.com latest   # FAILs unless the live api/ code equals HEAD's
#   scripts/smoke.sh https://fde-api.onrender.com 52c6029  # FAILs unless exactly that commit is live
# "latest" compares api/ trees, because Render only redeploys on api/ changes (buildFilter), so the
# live commit is legitimately older than HEAD after a docs-only push.
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
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $expected == latest ]]; then
  if [[ $commit == local ]]; then
    printf 'FAIL  %-10s target is not a Render deploy; "latest" only applies to Render\n' "commit"
    fail=1
  elif [[ -z $commit ]] || ! git -C "$root" cat-file -e "$commit^{commit}" 2>/dev/null; then
    printf 'FAIL  %-10s live commit %s unknown locally (git fetch?)\n' "commit" "${commit:-unknown}"
    fail=1
  elif git -C "$root" diff --quiet "$commit" HEAD -- api/; then
    printf 'PASS  %-10s live %s has the same api/ code as HEAD %s\n' "commit" "${commit:0:7}" \
      "$(git -C "$root" rev-parse --short HEAD)"
  else
    printf 'FAIL  %-10s live %s has different api/ code than HEAD %s\n' "commit" "${commit:0:7}" \
      "$(git -C "$root" rev-parse --short HEAD)"
    fail=1
  fi
elif [[ -n $expected ]]; then
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
