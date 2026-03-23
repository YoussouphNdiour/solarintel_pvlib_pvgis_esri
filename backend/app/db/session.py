"""Async SQLAlchemy engine and session factory for SolarIntel v2.

Provides:
- A module-level ``async_engine`` created from the settings DATABASE_URL.
- ``AsyncSessionLocal``: an ``async_sessionmaker`` for creating sessions.
- ``get_async_db()``: FastAPI dependency that yields a transactional session.
- ``create_all_tables()``: helper used only in tests and initial setup.
- ``dispose_engine()``: graceful teardown called during application shutdown.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def _build_engine() -> AsyncEngine:
    """Construct the async SQLAlchemy engine from application settings.

    Returns:
        A configured ``AsyncEngine`` instance. The engine is not connected
        until the first query is executed.
    """
    settings = get_settings()
    return create_async_engine(
        str(settings.database_url),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        echo=settings.debug,
        future=True,
    )


# Module-level singletons — created once per process.
async_engine: AsyncEngine = _build_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield a transactional async database session.

    The session is committed automatically if the request handler returns
    without raising an exception. Any exception causes a rollback.

    Yields:
        An ``AsyncSession`` bound to the module-level engine.

    Example::

        @router.get("/users/{user_id}")
        async def get_user(
            user_id: UUID,
            db: AsyncSession = Depends(get_async_db),
        ) -> UserSchema:
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """Create all tables defined in the SQLAlchemy metadata.

    This function is intended for use in tests and initial local setup only.
    Production schema changes must be managed exclusively through Alembic
    migrations.

    Warning:
        Do **not** call this function in production — use
        ``alembic upgrade head`` instead.
    """
    # Import models so their metadata is registered with Base before create_all.
    from app.models import Base  # noqa: PLC0415

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Drop all tables managed by SQLAlchemy metadata.

    Used exclusively in the test suite teardown to leave a clean database
    between test runs.

    Warning:
        This is **destructive**. Never call in production or staging.
    """
    from app.models import Base  # noqa: PLC0415

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def dispose_engine() -> None:
    """Dispose the async engine and release all pooled connections.

    Call this during application shutdown (``lifespan`` context manager)
    to ensure all database connections are returned to the OS cleanly.
    """
    await async_engine.dispose()
