"""Apply numbered SQL migrations from db/migrations/ to DATABASE_URL, each once, in name order.

Run from api/:  uv run python -m db.migrate
Applied file names are recorded in public.schema_migrations (Supabase keeps its own copies in
auth/realtime, hence the explicit schema); re-running is a no-op.
"""

from pathlib import Path

import psycopg

from config import get_settings

MIGRATIONS = Path(__file__).parent / "migrations"


def main() -> None:
    files = sorted(MIGRATIONS.glob("*.sql"))
    with psycopg.connect(get_settings().database_url) as conn:
        conn.execute(
            "create table if not exists public.schema_migrations ("
            " name text primary key, applied_at timestamptz not null default now())"
        )
        conn.execute("alter table public.schema_migrations enable row level security")
        applied = {name for (name,) in conn.execute("select name from public.schema_migrations")}

        pending = [f for f in files if f.name not in applied]
        for f in pending:
            # One transaction per file: a failing migration leaves no partial schema behind.
            with conn.transaction():
                conn.execute(f.read_bytes())  # bytes: file SQL isn't a LiteralString
                conn.execute("insert into public.schema_migrations (name) values (%s)", (f.name,))
            print(f"applied  {f.name}")

    print(f"done: {len(pending)} applied, {len(files) - len(pending)} already up to date")


if __name__ == "__main__":
    main()
