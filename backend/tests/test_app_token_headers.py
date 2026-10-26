"""Behavioral tests for application token header compatibility."""

import unittest

from fastapi import Request

from auth.dependencies import extract_app_token


def request_with_headers(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/me",
            "headers": headers,
            "client": ("127.0.0.1", 4321),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


class AppTokenHeaderTests(unittest.TestCase):
    def test_legacy_token_header_remains_supported(self) -> None:
        request = request_with_headers([(b"token", b"legacy-token")])

        self.assertEqual(extract_app_token(request), "legacy-token")

    def test_bearer_authorization_header_is_supported(self) -> None:
        request = request_with_headers([(b"authorization", b"Bearer bearer-token")])

        self.assertEqual(extract_app_token(request), "bearer-token")

    def test_other_authorization_schemes_are_rejected(self) -> None:
        request = request_with_headers([(b"authorization", b"Basic credentials")])

        self.assertIsNone(extract_app_token(request))


if __name__ == "__main__":
    unittest.main()
