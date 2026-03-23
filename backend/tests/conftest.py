"""Pytest configuration and shared fixtures for SolarIntel v2 tests.

Provides:
- ``async_session``: An ``AsyncSession`` backed by an in-memory SQLite
  database. All tables are created before each test and dropped afterwards
  so tests are fully isolated.
- ``async_redis``: A fake Redis client backed by ``fakeredis`` (or a
  ``unittest.mock.AsyncMock`` fallback when fakeredis is unavailable).

Design choices:
- SQLite with ``aiosqlite`` is used instead of PostgreSQL so the test suite
  runs without any external services (CI-friendly).
- The ``JSONB`` column type degrades gracefully to ``JSON`` under SQLite
  because we override the dialect type mapping in each engine.
- ``asyncio_mode = "auto"`` is set in ``pyproject.toml``, so no explicit
  ``@pytest.mark.asyncio`` decorators are needed.
- ``pytest_configure`` injects stub environment variables required by
  ``Settings`` before any app modules are imported, so no real PostgreSQL
  or Redis server is needed during the test run.
"""

from __future__ import annotations

import os


def pytest_configure(config: object) -> None:  # noqa: ANN001 — pytest type
    """Inject stub environment variables before app modules are imported.

    ``app.db.session`` creates the SQLAlchemy engine at module-import time,
    which triggers ``get_settings()`` and therefore requires all ``Settings``
    required fields to be present.  We supply safe dummy values here so that
    the engine is constructed (but never actually connected to) during tests.
    The real DB is replaced by an in-memory SQLite via the ``async_session``
    fixture.
    """
    _REQUIRED_ENV: dict[str, str] = {
        "SECRET_KEY": "testsecretkey_at_least_32_chars_long_for_tests_only",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
        "ARCGIS_API_KEY": "arcgis-test-key",
    }
    for key, value in _REQUIRED_ENV.items():
        os.environ.setdefault(key, value)

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.types import JSON, TypeDecorator

# ── Import all models to register them with Base.metadata ────────────────────
from app.models import Base  # noqa: F401 — side-effect: registers all tables


# ── SQLite-compatible JSONB shim ──────────────────────────────────────────────

class _JsonbCompat(TypeDecorator):  # type: ignore[type-arg]
    """A JSON-compatible drop-in for JSONB when running under SQLite.

    SQLite does not understand the PostgreSQL JSONB type, so this decorator
    serialises Python dicts/lists to JSON strings on write and deserialises
    them on read.
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        """Serialise a Python object to a JSON string for storage."""
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        """Deserialise a JSON string back to a Python object."""
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value


def _patch_jsonb_for_sqlite(metadata: Any) -> None:
    """Replace JSONB columns with ``_JsonbCompat`` in the given metadata.

    Iterates all tables and columns in ``metadata`` and substitutes any
    ``JSONB`` type with ``_JsonbCompat`` so that SQLite can handle them.

    Args:
        metadata: A ``sqlalchemy.MetaData`` instance whose column types
            should be patched in-place.
    """
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = _JsonbCompat()


# ── Async session fixture ─────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated async database session for each test.

    Lifecycle:
    1. Create an in-memory SQLite engine (``aiosqlite`` driver).
    2. Patch all JSONB columns to ``_JsonbCompat`` for SQLite compatibility.
    3. Create all tables defined in ``Base.metadata``.
    4. Yield a session bound to the engine.
    5. Drop all tables after the test completes.

    Yields:
        A fully configured ``AsyncSession`` backed by SQLite in-memory.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Patch JSONB → JSON-compatible type before creating tables.
    _patch_jsonb_for_sqlite(Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ── Fake Redis fixture ────────────────────────────────────────────────────────

@pytest_asyncio.fixture()
async def async_redis() -> AsyncGenerator[Any, None]:
    """Return a fake Redis client for unit tests.

    Tries to use ``fakeredis`` for a realistic in-memory implementation.
    Falls back to ``unittest.mock.AsyncMock`` if fakeredis is not installed.

    Yields:
        A Redis-compatible async client (``FakeRedis`` or ``AsyncMock``).
    """
    try:
        import fakeredis.aioredis as fakeredis  # type: ignore[import]

        redis = fakeredis.FakeRedis(decode_responses=True)
        yield redis
        await redis.aclose()
    except ImportError:
        # Minimal AsyncMock shim that satisfies the cache round-trip test.
        store: dict[str, str] = {}

        mock = AsyncMock()
        mock.set = AsyncMock(side_effect=lambda k, v, ex=None: store.__setitem__(k, v))
        mock.setex = AsyncMock(
            side_effect=lambda k, t, v: store.__setitem__(k, v)
        )
        mock.get = AsyncMock(side_effect=lambda k: store.get(k))
        mock.delete = AsyncMock(side_effect=lambda k: store.pop(k, None))
        mock.aclose = AsyncMock()
        yield mock
