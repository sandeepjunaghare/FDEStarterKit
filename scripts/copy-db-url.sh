#!/usr/bin/env bash
# Copy DATABASE_URL from the repo-root .env to the clipboard, ready to paste into a dashboard (Render).
# Strips the KEY= prefix and quotes, adds sslmode=require if missing, refuses <placeholders>,
# and prints the result with the password masked. Usage: scripts/copy-db-url.sh
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$root/.env"

die() {
  echo "copy-db-url: $*" >&2
  exit 1
}

[[ -f $env_file ]] || die "no .env at $env_file (cp .env.example .env)"
url=$(grep -m1 '^DATABASE_URL=' "$env_file" | cut -d= -f2- | tr -d "'\"\r\n") || true
[[ -n $url ]] || die "no DATABASE_URL= line in .env"
[[ $url == postgresql://* || $url == postgres://* ]] || die "DATABASE_URL in .env must start with postgresql://"
[[ $url != *'<'* && $url != *'>'* ]] || die "DATABASE_URL in .env still has a <placeholder>"

if [[ $url != *sslmode=* ]]; then
  if [[ $url == *'?'* ]]; then url+="&sslmode=require"; else url+="?sslmode=require"; fi
fi

printf '%s' "$url" | pbcopy
echo "copied: $(sed -E 's#(://[^:]+:)[^@]+@#\1***@#' <<<"$url")"
echo "paste it as the DATABASE_URL value now; copying anything else first replaces it"
