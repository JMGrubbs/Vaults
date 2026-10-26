"""Regression tests for PostgreSQL bootstrap wiring."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = PROJECT_ROOT / "postgres" / "init-db.sh"
COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yaml"


class PostgresInitTests(unittest.TestCase):
    def test_init_script_has_valid_shell_syntax_and_creates_auth_resources(self) -> None:
        self.assertTrue(INIT_SCRIPT.is_file(), "PostgreSQL init script is missing")

        subprocess.run(
            ["sh", "-n", str(INIT_SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
        )

        contents = INIT_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("CREATE ROLE", contents)
        self.assertIn("CREATE DATABASE", contents)
        self.assertIn("CREATE SCHEMA IF NOT EXISTS", contents)
        self.assertIn("ALTER ROLE", contents)
        self.assertIn("POSTGRES_APP_USER", contents)
        self.assertIn("POSTGRES_APP_PASSWORD", contents)
        self.assertIn("POSTGRES_APP_DB", contents)
        self.assertIn("DATABASE_URL", contents)

    def test_database_url_credentials_are_parsed_at_the_last_at_sign(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            capture_file = temp_path / "captured-environment"
            fake_psql = temp_path / "psql"
            fake_psql.write_text(
                "#!/bin/sh\n"
                'printf "%s|%s|%s\\n" "$INIT_DB_USER" "$INIT_DB_PASSWORD" '
                '"$INIT_DB_NAME" >> "$CAPTURE_FILE"\n'
                "cat >/dev/null\n",
                encoding="utf-8",
            )
            fake_psql.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{temp_path}:{environment['PATH']}",
                    "CAPTURE_FILE": str(capture_file),
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "bootstrap-password",
                    "POSTGRES_DB": "postgres",
                    "DATABASE_URL": (
                        "postgresql+asyncpg://app_user:p@ss%3Aword"
                        "@postgres:5432/app_database"
                    ),
                }
            )

            subprocess.run(
                ["sh", str(INIT_SCRIPT)],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(
                capture_file.read_text(encoding="utf-8").splitlines(),
                [
                    "app_user|p@ss:word|app_database",
                    "app_user|p@ss:word|app_database",
                ],
            )

    def test_compose_mounts_the_init_script_read_only(self) -> None:
        contents = COMPOSE_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "./postgres/init-db.sh:/docker-entrypoint-initdb.d/10-init-auth.sh:ro",
            contents,
        )
        self.assertIn("postgres-init:", contents)
        self.assertIn("env_file:", contents)
        self.assertIn("./backend/.env", contents)
        self.assertIn("condition: service_completed_successfully", contents)


if __name__ == "__main__":
    unittest.main()
