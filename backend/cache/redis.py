from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from core.config import settings


class RedisManager:
    """
    Manages a reusable async Redis connection pool + client for the API.
    """

    def __init__(self) -> None:
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None

    async def connect(self) -> None:
        """
        Initialize the Redis connection pool and client once.
        Safe to call multiple times.
        """
        if self._client is not None:
            return

        self._pool = ConnectionPool.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
        )

        self._client = Redis(connection_pool=self._pool)

        # Validate connection on startup
        await self._client.ping()

    async def disconnect(self) -> None:
        """
        Close the Redis client and pool cleanly on shutdown.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None

    def get_client(self) -> Redis:
        """
        Return the initialized Redis client.
        """
        if self._client is None:
            raise RuntimeError("Redis client has not been initialized.")
        return self._client


redis_manager = RedisManager()