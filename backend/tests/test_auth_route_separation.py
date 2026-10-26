"""Behavioral tests for the Vault and application authentication contracts."""

import unittest

from api.v1.api import api_router


def route_methods() -> set[tuple[str, str]]:
    return {
        (route.path, method)
        for route in api_router.routes
        for method in getattr(route, "methods", set())
    }


class AuthRouteSeparationTests(unittest.TestCase):
    def test_vault_browser_routes_have_their_own_namespace(self) -> None:
        routes = route_methods()

        self.assertIn(("/vault/auth/register", "POST"), routes)
        self.assertIn(("/vault/auth/login", "POST"), routes)
        self.assertIn(("/vault/auth/me", "GET"), routes)
        self.assertIn(("/vault/auth/logout", "POST"), routes)

    def test_application_routes_keep_the_legacy_auth_namespace(self) -> None:
        routes = route_methods()

        self.assertIn(("/auth/login", "POST"), routes)
        self.assertIn(("/auth/me", "GET"), routes)
        self.assertIn(("/auth/me", "POST"), routes)
        self.assertIn(("/auth/logout", "POST"), routes)
        self.assertIn(("/auth/blacklist", "POST"), routes)


if __name__ == "__main__":
    unittest.main()
