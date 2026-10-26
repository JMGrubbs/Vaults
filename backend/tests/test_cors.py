"""Regression tests for credentialed browser CORS."""

import unittest

from main import app


class CredentialedCorsTests(unittest.TestCase):
    def test_cors_uses_explicit_origins_for_cookie_auth(self) -> None:
        cors_middleware = next(
            middleware
            for middleware in app.user_middleware
            if middleware.cls.__name__ == "CORSMiddleware"
        )

        self.assertNotIn("*", cors_middleware.kwargs["allow_origins"])
        self.assertIn("http://localhost:5173", cors_middleware.kwargs["allow_origins"])
        self.assertTrue(cors_middleware.kwargs["allow_credentials"])


if __name__ == "__main__":
    unittest.main()
