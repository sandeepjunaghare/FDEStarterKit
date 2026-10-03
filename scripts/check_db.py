# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "psycopg[binary]>=3.2",
#     "pgvector>=0.3",
#     "numpy",
#     "python-dotenv",
# ]
# ///
"""Supabase + pgvector smoke test, using the same driver stack as the API.

Checks, in order:
  1. connect   : DATABASE_URL reaches Supabase over SSL (session pooler)
  2. extension : pgvector is installed
  3. roundtrip : vectors insert and cosine nearest-neighbour search is correct

Uses a temp table only, so nothing persists. Exits non-zero on the first failure.

Run from anywhere:
  uv run --script scripts/check_db.py
"""

import os
import re
import sys
from pathlib import Path

import numpy as np
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

ROOT = Path(__file__).resolve().parents[1]


def masked(url: str) -> str:
    """Hide the password in a connection URL for safe printing."""
    return re.sub(r"(://[^:/]+:)[^@]+@", r"\1***@", url)


def fail(step: str, err: object) -> None:
    print(f"FAIL [{step}] {err}")
    sys.exit(1)


def main() -> None:
    load_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        fail("config", f"DATABASE_URL not set (looked in env and {ROOT / '.env'})")
    print(f"target: {masked(url)}")

    try:
        conn = psycopg.connect(url, connect_timeout=10)
    except psycopg.Error as e:
        fail("connect", e)

    with conn:
        version, user = conn.execute("select version(), current_user").fetchone()
        if "Postgres.app" in version:
            fail("connect", "reached local Postgres.app, not Supabase — check DATABASE_URL")
        # Client-side check: behind the pooler, server-side pg_stat_ssl describes the
        # pooler→Postgres hop, not this connection.
        ssl = conn.pgconn.ssl_in_use
        if not ssl:
            fail("connect", "connection is not encrypted — add ?sslmode=require to DATABASE_URL")
        print(f"PASS [connect]   user={user} ssl={ssl} | {version.split(',')[0]}")

        row = conn.execute(
            "select extversion from pg_extension where extname = 'vector'"
        ).fetchone()
        if not row:
            fail(
                "extension",
                "pgvector missing — run: create extension vector with schema extensions;",
            )
        print(f"PASS [extension] pgvector {row[0]}")

        register_vector(conn)
        conn.execute("create temp table check_db (id int, v vector(3))")
        with conn.cursor() as cur:
            cur.executemany(
                "insert into check_db values (%s, %s)",
                [(1, np.array([1, 0, 0])), (2, np.array([0, 1, 0])), (3, np.array([0.9, 0.1, 0]))],
            )
        ids = [
            r[0]
            for r in conn.execute(
                "select id from check_db order by v <=> %s limit 2", (np.array([1, 0, 0]),)
            )
        ]
        if ids != [1, 3]:
            fail("roundtrip", f"expected nearest [1, 3], got {ids}")
        print(f"PASS [roundtrip] cosine nearest neighbours {ids}")

    print("OK: Supabase + pgvector ready")


if __name__ == "__main__":
    main()
