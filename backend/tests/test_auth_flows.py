"""Behavioral tests for application-token and Vault-cookie authentication."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, Request, Response

from api.v1.endpoints import auth, vault_auth
from schemas.user import UserCreate, UserLogin


class FakeCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    async def set_json(self, key: str, value, ttl: int | None = None) -> bool:
        self.values[key] = value
        return True


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, value) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        return None


class AuthFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user = SimpleNamespace(
            id="b197a8c0-d020-4e38-8e2a-8d55b3c9476e",
            email="person@example.com",
            is_active=True,
            is_admin=False,
        )
        self.credentials = UserLogin(
            email="PERSON@example.com",
            password="Valid1!Password",
        )

    @staticmethod
    def request() -> Request:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/vault/auth/login",
                "headers": [],
                "client": ("127.0.0.1", 4321),
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )
        request.state.request_id = "auth-flow-test"
        return request

    async def test_vault_login_sets_cookie_without_returning_token(self) -> None:
        response = Response()
        cache = FakeCache()
        session = FakeSession()

        with (
            patch.object(vault_auth, "login_user", new=AsyncMock(return_value=self.user)),
            patch.object(vault_auth, "create_access_token", return_value="signed-token"),
        ):
            result = await vault_auth.login_route(
                request=self.request(),
                response=response,
                credentials=self.credentials,
                session=session,
                cache=cache,
            )

        set_cookie = response.headers["set-cookie"]
        self.assertEqual(result.username, "person@example.com")
        self.assertNotIn("signed-token", result.model_dump().values())
        self.assertIn("signed-token", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("Secure", set_cookie)
        self.assertIn(f"auth:user:{self.user.id}", cache.values)

    async def test_application_login_returns_token_without_cookie_response(self) -> None:
        cache = FakeCache()
        session = FakeSession()

        with (
            patch.object(auth, "login_user", new=AsyncMock(return_value=self.user)),
            patch.object(auth, "create_access_token", return_value="application-token"),
        ):
            result = await auth.login_route(
                request=self.request(),
                credentials=self.credentials,
                session=session,
                cache=cache,
            )

        self.assertEqual(result.username, "person@example.com")
        self.assertEqual(result.token, "application-token")
        self.assertIn(f"auth:user:{self.user.id}", cache.values)

    async def test_vault_registration_reports_duplicate_email_as_conflict(self) -> None:
        new_user = UserCreate(
            email="person@example.com",
            password="Valid1!Password",
        )

        with patch.object(
            vault_auth,
            "register_user",
            new=AsyncMock(return_value={"message": "User with this email already exists"}),
        ):
            with self.assertRaises(HTTPException) as raised:
                await vault_auth.register_route(self.request(), new_user, object())

        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
