"""FastAPI application entrypoint."""
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.logging import setup_logging
from app.database import engine
from app.api import messages, trace, operations, health

setup_logging()
log = logging.getLogger(__name__)
settings = get_settings()


def _run_migrations() -> bool:
    """
    Run Alembic migrations synchronously at startup.

    Passes both DATABASE_URL (asyncpg) and DATABASE_URL_SYNC (psycopg2/plain)
    so migrations/env.py can pick the right driver.
    Returns True on success.
    """
    env = os.environ.copy()

    # Provide the async URL — env.py will use it for online migration
    env["DATABASE_URL"] = settings.database_url

    # Also provide a sync fallback (env.py converts as needed)
    env["DATABASE_URL_SYNC"] = settings.database_url_sync

    # cwd must be the backend root (where alembic.ini lives)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        log.error("Alembic migration timed out after 120s")
        return False
    except Exception as exc:
        log.error("Failed to launch Alembic: %s", exc)
        return False

    if result.returncode != 0:
        log.error(
            "Alembic migration FAILED (exit %d):\nstdout: %s\nstderr: %s",
            result.returncode,
            result.stdout[-1000:],
            result.stderr[-1000:],
        )
        return False

    log.info("Alembic: %s", result.stdout.strip() or "migrations up to date")
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting %s", settings.app_name)

    # Step 1: run migrations — REQUIRED before anything else
    ok = _run_migrations()
    if not ok:
        log.error(
            "Migrations failed — tables may not exist. "
            "Check DATABASE_URL and Alembic configuration."
        )
        # Still start up so /health can report degraded status

    # Step 2: seed reference data (fully idempotent — safe to call every startup)
    from app.database import get_db_context
    from app.services.seed import seed_all
    try:
        async with get_db_context() as db:
            await seed_all(db)
    except Exception as exc:
        log.warning("Seeding encountered an error (non-fatal): %s", exc)

    yield

    log.info("Shutting down.")
    await engine.dispose()


app = FastAPI(
    title="Rider Payout Dispute Desk",
    description="AI-powered payout dispute resolution for QuickDrop riders",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,      tags=["health"])
app.include_router(messages.router,    tags=["messages"])
app.include_router(trace.router,       tags=["trace"])
app.include_router(operations.router,  tags=["operations"])


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc)},
    )
