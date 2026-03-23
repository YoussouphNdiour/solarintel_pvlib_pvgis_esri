"""Async Redis client for SolarIntel v2.

Wraps ``redis.asyncio`` to provide a simple, typed caching API used across
the application for:
- PVGIS irradiance data (long TTL — 30 days)
- JWT refresh / session tokens (24-hour TTL)
- Senelec tariff snapshots (7-day TTL)

Usage::

    from app.db.redis import RedisClient

    client = RedisClient()
    await client.cache_set("pvgis:14.7:-17.4", json_str, PVGIS_TTL)
    result = await client.cache_get("pvgis:14.7:-17.4")
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings

# ── TTL constants (seconds) ───────────────────────────────────────────────────
PVGIS_TTL: int = 60 * 60 * 24 * 30  # 30 days — PVGIS data changes rarely
SESSION_TTL: int = 60 * 60 * 24  # 24 hours — JWT refresh token window
TARIFF_TTL: int = 60 * 60 * 24 * 7  # 7 days — tariff tables update infrequently


class RedisClient:
    """Async Redis cache client.

    Instantiate once and reuse across the application lifetime.
    Internally creates a single ``Redis`` connection pool on first access.

    Attributes:
        _client: The underlying ``redis.asyncio.Redis`` pool instance;
            lazily initialised on first call to ``get_client()``.
    """

    def __init__(self) -> None:
        """Initialise without connecting — connection is deferred."""
        self._client: aioredis.Redis | None = None  # type: ignore[type-arg]

    def get_client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        """Return (and lazily create) the Redis connection pool.

        The pool is created once per ``RedisClient`` instance and reused
        for all subsequent operations.

        Returns:
            A configured ``redis.asyncio.Redis`` connection pool.
        """
        if self._client is None:
            settings = get_settings()
            self._client = aioredis.from_url(
                str(settings.redis_url),
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def cache_get(self, key: str) -> str | None:
        """Retrieve a cached string value by key.

        Args:
            key: The Redis key to look up.

        Returns:
            The cached string value, or ``None`` if the key does not exist
            or has expired.
        """
        client = self.get_client()
        value: str | None = await client.get(key)
        return value

    async def cache_set(
        self,
        key: str,
        value: str,
        ttl_seconds: int,
    ) -> None:
        """Store a string value in Redis with a TTL.

        Args:
            key: The Redis key under which to store the value.
            value: The string payload to cache.
            ttl_seconds: Time-to-live in seconds; the key expires automatically
                after this duration.
        """
        client = self.get_client()
        await client.setex(key, ttl_seconds, value)

    async def cache_delete(self, key: str) -> None:
        """Delete a key from the cache immediately.

        Args:
            key: The Redis key to remove. A no-op if the key does not exist.
        """
        client = self.get_client()
        await client.delete(key)

    async def close(self) -> None:
        """Close the Redis connection pool gracefully.

        Call during application shutdown to release connections cleanly.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Module-level singleton — import and reuse this across the application.
redis_client: RedisClient = RedisClient()
