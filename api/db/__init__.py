"""Supabase Postgres access: the shared async pool and the DB health probe."""

from psycopg_pool import AsyncConnectionPool

from config import Settings


def create_pool(settings: Settings) -> AsyncConnectionPool:
    """Build the app-wide pool, unopened; the app lifespan opens and closes it."""
    return AsyncConnectionPool(
        settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
        timeout=settings.db_timeout_s,
        kwargs={"connect_timeout": int(settings.db_timeout_s)},
        open=False,
    )


async def check_db(pool: AsyncConnectionPool) -> str | None:
    """Round-trip to the DB; return the pgvector version, or None if it isn't installed.

    Raises psycopg.Error (incl. PoolTimeout) when the DB is unreachable.
    """
    async with pool.connection() as conn:
        cur = await conn.execute("select extversion from pg_extension where extname = 'vector'")
        row = await cur.fetchone()
    return row[0] if row else None


class SmokeCheckError(Exception):
    """The DB answered, but a smoke step returned the wrong result."""


async def smoke_roundtrip(pool: AsyncConnectionPool) -> float:
    """Write a row, read it back and find it by vector similarity, then roll everything back.

    Proves insert/select/pgvector permissions on a real table without persisting anything.
    Returns the cosine distance of the nearest match (0.0 for an exact hit).
    Raises psycopg.Error (e.g. UndefinedTable before migrations run) or SmokeCheckError.
    """
    probe = "[1,0,0]"
    async with pool.connection() as conn, conn.transaction(force_rollback=True):
        cur = await conn.execute(
            "insert into smoke_checks (note, embedding) values ('smoke', %s::vector) returning id",
            (probe,),
        )
        inserted = await cur.fetchone()
        if inserted is None:
            raise SmokeCheckError("insert returned no id")

        cur = await conn.execute("select note from smoke_checks where id = %s", (inserted[0],))
        read = await cur.fetchone()
        if read is None or read[0] != "smoke":
            raise SmokeCheckError("read-back did not return the inserted row")

        cur = await conn.execute(
            "select id, embedding <=> %s::vector from smoke_checks order by 2 limit 1", (probe,)
        )
        nearest = await cur.fetchone()
        if nearest is None or nearest[0] != inserted[0]:
            raise SmokeCheckError("similarity search did not return the inserted row")
    return float(nearest[1])
