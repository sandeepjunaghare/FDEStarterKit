#!/usr/bin/env bash
# Deploy smoke test: liveness, deployed commit, DB + pgvector, and a write/read/vector-search
# roundtrip (rolled back).
# Usage: scripts/smoke.sh [base_url] [latest|expected_sha] [--wait]   (default http://localhost:8710)
#   scripts/smoke.sh https://fde-api.onrender.com latest          # FAILs unless live api/ code equals HEAD's
#   scripts/smoke.sh https://fde-api.onrender.com latest --wait   # first waits (up to 5 min) for that
#   scripts/smoke.sh https://fde-api.onrender.com 52c6029         # FAILs unless exactly that commit is live
# "latest" compares api/ trees, because Render only redeploys on api/ changes (buildFilter), so the
# live commit is legitimately older than HEAD after a docs-only push.
set -euo pipefail

wait=0
args=()
for a in "$@"; do
  if [[ $a == --wait ]]; then wait=1; else args+=("$a"); fi
done
base="${args[0]:-http://localhost:8710}"
base="${base%/}"
expected="${args[1]:-}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wait_limit=${SMOKE_WAIT_SECONDS:-300}
start=$SECONDS
fail=0
commit_msg=""

# Sets commit_msg; returns 0 when the live commit satisfies $expected (or nothing is expected).
commit_matches() {
  local commit=$1 head
  [[ -z $expected ]] && return 0
  if [[ $expected == latest ]]; then
    head=$(git -C "$root" rev-parse --short HEAD)
    if [[ $commit == local ]]; then
      commit_msg='target is not a Render deploy; "latest" only applies to Render'
    elif [[ -z $commit ]] || ! git -C "$root" cat-file -e "$commit^{commit}" 2>/dev/null; then
      commit_msg="live commit ${commit:-unknown} unknown locally (git fetch?)"
    elif git -C "$root" diff --quiet "$commit" HEAD -- api/; then
      commit_msg="live ${commit:0:7} has the same api/ code as HEAD $head"
      return 0
    else
      commit_msg="live ${commit:0:7} has different api/ code than HEAD $head"
    fi
  elif [[ -n $commit && ($commit == "$expected"* || $expected == "$commit"*) ]]; then
    # Prefix match either way, so short and full SHAs compare equal.
    commit_msg="live commit matches ${expected:0:7}"
    return 0
  else
    commit_msg="live is ${commit:-unknown}, expected ${expected:0:7}"
  fi
  return 1
}

live_commit() {
  curl -sf --max-time 10 "$base/version" | sed -n 's/.*"commit":"\([^"]*\)".*/\1/p'
}

echo "target: $base"

if ((wait)); then
  # Wait until the service answers AND (if expected) serves the right code: after a push, the old
  # deploy stays healthy while the new one builds.
  printf 'wait  up to %ss for a healthy deploy%s ' "$wait_limit" "${expected:+ of the expected code}"
  until curl -sf -o /dev/null --max-time 5 "$base/health" && commit_matches "$(live_commit || true)"; do
    if ((SECONDS - start >= wait_limit)); then
      echo
      echo "FAIL  wait       not ready after ${wait_limit}s${commit_msg:+ ($commit_msg)}"
      echo "      wrong URL? Render may have added a suffix: copy it from the service page"
      exit 1
    fi
    printf .
    sleep 3
  done
  echo " ready after $((SECONDS - start))s"
fi

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

check health GET /health
check version GET /version
if [[ -n $expected ]]; then
  commit=$(sed -n 's/.*"commit":"\([^"]*\)".*/\1/p' <<<"$last_body")
  if commit_matches "$commit"; then
    printf 'PASS  %-10s %s\n' "commit" "$commit_msg"
  else
    printf 'FAIL  %-10s %s\n' "commit" "$commit_msg"
    fail=1
  fi
fi
check health/db GET /health/db
check smoke POST /smoke
echo "elapsed: $((SECONDS - start))s"

if ((fail)); then
  echo "SMOKE FAILED"
  echo "  [000]                 -> server unreachable, or still waking/deploying: retry, or add --wait"
  echo "  503 UndefinedTable    -> migrations not applied: cd api && uv run python -m db.migrate"
  echo "  503 PoolTimeout/other -> DATABASE_URL wrong or missing in this environment"
  echo "  commit mismatch       -> new deploy not live yet (CI or build still running): add --wait"
  exit 1
fi
echo "SMOKE OK"
