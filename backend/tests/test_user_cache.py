"""Behavioral tests for Redis-backed authenticated user lookups."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from auth.dependencies import USER_CACHE_TTL_SECONDS, get_cached_user


class FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self.set_calls: list[tuple[str, object, int | None]] = []

    async def get_json(self, key: str):
        return self.values.get(key)

    async def set_json(self, key: str, value, ttl: int | None = None) -> bool:
        self.values[key] = value
        self.set_calls.append((key, value, ttl))
        return True

    async def delete_json(self, key: str) -> int:
        return int(self.values.pop(key, None) is not None)


class UserCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_user_lookup_is_served_from_redis_cache(self) -> None:
        user_id = "b197a8c0-d020-4e38-8e2a-8d55b3c9476e"
        database_user = SimpleNamespace(
            id=user_id,
            email="person@example.com",
            is_active=True,
            is_admin=False,
        )
        cache = FakeCache()

        with patch(
            "auth.dependencies.get_user_by_id",
            new=AsyncMock(return_value=database_user),
        ) as database_lookup:
            first_result = await get_cached_user(user_id, object(), cache)
            second_result = await get_cached_user(user_id, object(), cache)

        self.assertEqual(first_result, second_result)
        self.assertEqual(second_result.email, "person@example.com")
        database_lookup.assert_awaited_once()
        self.assertEqual(cache.set_calls[0][2], USER_CACHE_TTL_SECONDS)


if __name__ == "__main__":
    unittest.main()
