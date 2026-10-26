"""Behavioral tests for authentication audit events."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from api.v1.endpoints import auth
from fastapi import Request

from repositories.auth_events import record_auth_event


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commit = AsyncMock()

    def add(self, value) -> None:
        self.added.append(value)


def request_with_context() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": [(b"user-agent", b"audit-test")],
            "client": ("127.0.0.1", 4321),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    request.state.request_id = "request-123"
    return request


class AuthEventTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_stores_a_fingerprint_instead_of_the_raw_token(self) -> None:
        session = FakeSession()
        request = request_with_context()

        await record_auth_event(
            session=session,
            event_type="token_use",
            request=request,
            user_id="b197a8c0-d020-4e38-8e2a-8d55b3c9476e",
            token="raw-jwt-must-not-be-stored",
        )

        event = session.added[0]
        self.assertEqual(event.event_type, "token_use")
        self.assertEqual(event.request_id, "request-123")
        self.assertEqual(event.ip_address, "127.0.0.1")
        self.assertEqual(event.user_agent, "audit-test")
        self.assertNotEqual(event.token_fingerprint, "raw-jwt-must-not-be-stored")
        self.assertEqual(len(event.token_fingerprint), 64)
        session.commit.assert_awaited_once()

    async def test_application_login_records_a_successful_signin(self) -> None:
        credentials = SimpleNamespace(email="person@example.com", password="Valid1!Password")
        user = SimpleNamespace(
            id="b197a8c0-d020-4e38-8e2a-8d55b3c9476e",
            email="person@example.com",
            is_active=True,
            is_admin=False,
        )
        request = request_with_context()

        with (
            patch.object(auth, "login_user", new=AsyncMock(return_value=user)),
            patch.object(auth, "cache_user_profile", new=AsyncMock()),
            patch.object(auth, "create_access_token", return_value="application-token"),
            patch.object(auth, "record_auth_event", new=AsyncMock()) as record_event,
        ):
            await auth.login_route(
                request=request,
                credentials=credentials,
                session=object(),
                cache=SimpleNamespace(),
            )

        self.assertEqual(record_event.await_args.kwargs["event_type"], "signin_success")
        self.assertEqual(record_event.await_args.kwargs["user_id"], user.id)
        self.assertEqual(record_event.await_args.kwargs["token"], "application-token")


if __name__ == "__main__":
    unittest.main()
