"""Behavioral tests for retry-safe application token revocation."""

import unittest
from unittest.mock import AsyncMock

from sqlalchemy.exc import IntegrityError

from repositories.jwt_token_blacklist import insert_blacklisted_token


class FakeCache:
    def __init__(self) -> None:
        self.values = {}

    async def set_json(self, key: str, value, ttl: int | None = None) -> bool:
        self.values[key] = (value, ttl)
        return True


class DuplicateSession:
    def __init__(self) -> None:
        self.rollback = AsyncMock()

    def add(self, value) -> None:
        return None

    async def commit(self) -> None:
        raise IntegrityError("duplicate token", {}, Exception("unique constraint"))


class AppBlacklistTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_blacklist_is_successful_and_cached(self) -> None:
        cache = FakeCache()
        session = DuplicateSession()

        result = await insert_blacklisted_token(session, "same-jti", cache)

        self.assertTrue(result)
        session.rollback.assert_awaited_once()
        self.assertEqual(cache.values["blacklisted_token:same-jti"], (True, 3600))


if __name__ == "__main__":
    unittest.main()
