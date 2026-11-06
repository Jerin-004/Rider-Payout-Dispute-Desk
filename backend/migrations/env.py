"""Alembic environment configuration — supports both sync and async PostgreSQL URLs."""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base  # noqa: E402
import app.models  # noqa: F401, E402

config = context.config

# ── Resolve the migration URL ───────────────────────────────────────────────
# Priority: DATABASE_URL_SYNC env > DATABASE_URL env > alembic.ini value
# We always need the *asyncpg* variant for online (async) mode and the
# *psycopg2* (plain postgresql://) variant for offline mode.

def _to_async_url(url: str) -> str:
    """Convert postgresql:// or postgresql+psycopg2:// → postgresql+asyncpg://"""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return url

def _to_sync_url(url: str) -> str:
    """Convert postgresql+asyncpg:// → postgresql://"""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url

# Pick the best available URL from environment
_raw_url = (
    os.environ.get("DATABASE_URL_SYNC")
    or os.environ.get("DATABASE_URL")
    or config.get_main_option("sqlalchemy.url", "")
)

ASYNC_URL = _to_async_url(_raw_url)
SYNC_URL  = _to_sync_url(_raw_url)

# Always override alembic config with the resolved URL
config.set_main_option("sqlalchemy.url", ASYNC_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Offline mode (generate SQL scripts) ─────────────────────────────────────
def run_migrations_offline() -> None:
    context.configure(
        url=SYNC_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (apply to live DB) ───────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(ASYNC_URL, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
