"""Keep the Vault browser isolated from application-token auth routes."""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SOURCE = PROJECT_ROOT / "frontend" / "src"


class FrontendAuthContractTests(unittest.TestCase):
    def test_frontend_uses_only_vault_auth_api_routes(self) -> None:
        service_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (FRONTEND_SOURCE / "services").glob("*.jsx")
        )
        provider_source = (
            FRONTEND_SOURCE / "auth" / "AuthProvider.jsx"
        ).read_text(encoding="utf-8")

        self.assertIn("/api/v1/vault/auth/login", service_sources)
        self.assertIn("/api/v1/vault/auth/register", service_sources)
        self.assertIn("/api/v1/vault/auth/me", service_sources)
        self.assertIn("/api/v1/vault/auth/logout", service_sources)
        self.assertNotIn('"/api/v1/auth/', service_sources)
        self.assertNotIn('"/api/v1/auth/', provider_source)


if __name__ == "__main__":
    unittest.main()
