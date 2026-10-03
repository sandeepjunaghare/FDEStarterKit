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
