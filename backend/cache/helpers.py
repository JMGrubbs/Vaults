from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis


class CacheHelper:
    redis: Redis

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def get_json(self, key: str) -> Any | None:
        """
        Get a JSON value from Redis and deserialize it.
        Returns None if the key does not exist.
        """
        raw_value = await self.redis.get(key)
        if raw_value is None:
            return None

        try:
            return json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Value for key '{key}' is not valid JSON") from exc

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Serialize a value as JSON and store it in Redis.
        ttl is in seconds.
        """
        serialized = json.dumps(value, default=str)
        return await self.redis.set(key, serialized, ex=ttl)

    async def delete_json(self, key: str) -> int:
        """
        Delete a key from Redis.
        Returns the number of keys deleted.
        """
        return await self.redis.delete(key)