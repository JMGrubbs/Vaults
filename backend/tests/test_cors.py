"""Regression tests for credentialed browser CORS."""

import json
import unittest
from unittest.mock import patch

from core.config import settings
from main import _cors_origins, app


class CredentialedCorsTests(unittest.TestCase):
    def test_cors_accepts_json_array_configuration(self) -> None:
        configured_origins = [
            "https://dauth.johnmgrubbs.io",
            "https://dvaults.johnmgrubbs.io",
        ]

        with patch.object(settings, "cors_origins", json.dumps(configured_origins)):
            self.assertEqual(_cors_origins(), configured_origins)

    def test_cors_accepts_comma_separated_configuration(self) -> None:
        with patch.object(
            settings,
            "cors_origins",
            "http://localhost:5175, https://dauth.johnmgrubbs.io",
        ):
            self.assertEqual(
                _cors_origins(),
                ["http://localhost:5175", "https://dauth.johnmgrubbs.io"],
            )

    def test_cors_uses_explicit_origins_for_cookie_auth(self) -> None:
        cors_middleware = next(
            middleware
            for middleware in app.user_middleware
            if middleware.cls.__name__ == "CORSMiddleware"
        )

        self.assertNotIn("*", cors_middleware.kwargs["allow_origins"])
        self.assertTrue(cors_middleware.kwargs["allow_credentials"])


if __name__ == "__main__":
    unittest.main()
