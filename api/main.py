"""FastAPI entrypoint: app lifespan (DB pool) and health routes."""

import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import get_settings
from db import check_db, create_pool

log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool(get_settings())
    # wait=False: start even if Supabase is down, so /health/db can report 503
    # instead of the container crash-looping.
    await pool.open(wait=False)
    app.state.pool = pool
    yield
    await pool.close()


app = FastAPI(title="FDE Starter Kit API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    """Liveness: the process is serving. Render's health check path — never touches the DB."""
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(request: Request) -> JSONResponse:
    """Readiness of the data layer: Supabase reachable and pgvector installed."""
    try:
        version = await check_db(request.app.state.pool)
    except psycopg.Error as e:
        # Full error goes to logs; the public response names only the class (no hostnames).
        log.warning("health/db failed: %r", e)
        return JSONResponse({"db": "error", "detail": type(e).__name__}, status_code=503)
    if version is None:
        return JSONResponse({"db": "ok", "pgvector": "missing"}, status_code=503)
    return JSONResponse({"db": "ok", "pgvector": version})
