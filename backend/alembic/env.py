"""Alembic async migration environment for SolarIntel v2.

Configured for async SQLAlchemy (asyncpg driver). Reads the DATABASE_URL
from application settings so the same configuration works across
development, staging, and production.

Usage::

    alembic upgrade head        # Apply all pending migrations
    alembic revision --autogenerate -m "add column"  # Generate new migration
    alembic downgrade -1        # Roll back one migration

References:
    https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# ── Import all models so their metadata is registered with Base ───────────────
# This import must happen before target_metadata is referenced.
from app.models import Base  # noqa: F401 — side-effect import
from app.core.config import get_settings

# Alembic Config object — provides access to alembic.ini values.
config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for --autogenerate support.
target_metadata = Base.metadata


def get_url() -> str:
    """Read the async DATABASE_URL from application settings.

    Returns:
        The full async database DSN string (``postgresql+asyncpg://...``).
    """
    return str(get_settings().database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection).

    Renders SQL to stdout or a file rather than executing against the DB.
    Useful for generating migration scripts to review before applying.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations using the provided synchronous connection.

    Args:
        connection: A synchronous ``Connection`` obtained from the async engine
            via ``run_sync``.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within it.

    Uses ``NullPool`` to avoid connection pool overhead during migrations,
    which are short-lived CLI invocations rather than long-running servers.
    """
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode by executing against a live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
