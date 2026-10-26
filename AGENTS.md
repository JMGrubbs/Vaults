# AGENTS.md

## Purpose

`Vaults` is the centralized identity service for the user's applications. It owns user credentials, password hashing, JWT issuance and validation, logout/revocation, and account administration. The React frontend is an account portal branded as Vaults.

The current HTTP contract is direct credential login with either an HttpOnly cookie or a legacy internal token response. OAuth 2.1-style authorization-code and rate-limit service modules exist, but no OAuth routes or browser helper are wired into this checkout. Do not describe PKCE login as implemented until the routes, client validation, frontend flow, and tests exist.

## Architecture

- `backend/`: Python 3.14 FastAPI API.
- PostgreSQL 17: users, token-revocation records, and Alembic state in the `auth` schema.
- Redis 7.4: revocation cache; the API requires Redis during startup.
- `frontend/`: React 19 + JavaScript/JSX + Vite 8 account UI.
- `docker-compose.yaml`: local runtime for the API, frontend, PostgreSQL, and Redis.
- Host ports: frontend `5175`, API `8002`, and PostgreSQL `5434`; Redis is not published to the host.

Read `APP_STRUCTURE_BLUEPRINT.md` before making cross-layer changes.

## Important Paths

- `backend/main.py`: FastAPI lifespan, request-ID middleware, CORS, and v1 router.
- `backend/api/v1/api.py`: route registration and the source of truth for active endpoint groups.
- `backend/api/v1/endpoints/`: authentication, user, and health handlers.
- `backend/auth/dependencies.py`: cookie/custom-header authentication and revocation.
- `backend/core/config.py` and `backend/core/security.py`: settings, JWTs, and password primitives.
- `backend/repositories/`: SQLAlchemy persistence access.
- `backend/services/`: registration plus currently unmounted OAuth scaffolding.
- `backend/models/` and `backend/alembic/`: `auth` schema models and migrations.
- `backend/tests/`: Python `unittest` tests.
- `frontend/src/App.jsx`: navigation and route definitions.
- `frontend/src/auth/AuthProvider.jsx`: browser session state and Axios response interception.
- `frontend/src/services/`: browser API wrappers.
- `frontend/src/pages/`: account, authentication, and placeholder app screens.

## Commands

Run all commands from `/home/lowery/auth-service` on `vm-work-dev-db`.

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 120 api frontend
docker compose run --rm --no-deps api python -m unittest discover -s tests -p 'test_*.py'
docker compose run --rm --no-deps frontend npm run lint
docker compose run --rm --no-deps frontend npm run build
docker compose down
```

There is no `frontend-test` Compose profile and no frontend test script at present. Do not document or invoke either until they are added.

Use `docker compose down` only when stopping the project is intended. Never add `-v` unless destructive volume removal is explicitly authorized.

## Configuration

- Never read, print, commit, or copy values from `.env`, `backend/.env`, or `frontend/.env` into tracked files or logs.
- Keep `.env.example`, `backend/.env.example`, and `frontend/.env.example` synchronized with the settings each layer actually reads. Examples must contain placeholders only.
- Root Compose interpolation uses `POSTGRES_MAIN_USER`, `POSTGRES_MAIN_PASSWORD`, and `POSTGRES_MAIN_DB` for bootstrap administration, plus `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD`, `POSTGRES_APP_DB`, and `POSTGRES_APP_SCHEMA` for the application role. Keep the application values synchronized with the backend `DATABASE_URL`.
- API settings require `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, and `COOKIE_KEY`; `ALGORITHM` and token lifetime have defaults.
- Browser code reads `VITE_AUTH_SERVICE_BACKEND_URL`. Every `VITE_` value is public and must never contain a secret.
- OAuth-related environment names exist but do not imply a working OAuth flow.
- Credentialed CORS uses the comma-separated `CORS_ORIGINS` setting; keep it restricted to exact browser origins.

## Current Authentication Contract

- Vault browser routes live below `/api/v1/vault/auth`; login and session lookup are cookie-only, registration is available at `/register`, and logout revokes the JWT and deletes the cookie.
- Other applications use `/api/v1/auth`; login returns the JWT in the JSON body and authenticated routes accept the legacy custom `token` header or `Authorization: Bearer`.
- The Vault frontend must never call `/api/v1/auth`; its browser API wrappers use `/api/v1/vault/auth` exclusively.
- Logout inserts the token `jti` into PostgreSQL and caches it in Redis. Active user profiles are cached in Redis for five minutes and invalidated when account state changes.
- `auth.auth_events` records sign-in, token-use, logout, and registration audit events. Store only token/email fingerprints; never persist raw JWTs, cookies, or passwords.
- Access-token payloads contain `sub`, `exp`, `iat`, and a unique `jti`.

Preserve these routes unless an intentional migration is documented and tested. Do not silently replace the custom internal header or response shape if existing callers may depend on them.

## Code and Security Conventions

- Use strict test-driven development for behavior changes: add one failing behavioral test, observe the expected failure, implement the smallest passing change, and rerun focused and full checks.
- Use typed Pydantic schemas and explicit HTTP status codes.
- Normalize email addresses and hash passwords; never store or log plaintext credentials, signing keys, cookies, authorization codes, or issued tokens.
- Keep secrets and bearer tokens out of URLs, redirects, and logs.
- If the OAuth flow is completed, require `state`, PKCE (`S256`), exact registered redirect matching, opaque short-lived single-use codes, and bindings to client, redirect URI, user, and PKCE challenge.
- Never use host suffixes, wildcards, partial matches, or arbitrary return URLs.
- Prefer HttpOnly/Secure/SameSite sessions. Calling apps with a backend should exchange codes server-side and establish their own cookie session rather than exposing bearer tokens to browser JavaScript.
- Keep CORS origins environment-driven when replacing the current wildcard. Credentialed browser requests require explicit origins.
- Preserve compatibility of existing API routes unless an intentional migration is documented.
- Keep React components accessible, responsive, keyboard-friendly, and explicit about loading/error states. Await async authentication actions and keep navigation targets synchronized with `frontend/src/App.jsx`.
- Clearly label mock UI data and disabled controls; do not present them as persisted account state.

## Verification Expectations

- Documentation-only changes: validate paths and commands against the repository, run `docker compose config --quiet`, and inspect the final diff.
- API changes: run the focused test first, then the full `backend/tests` suite.
- Frontend changes: run ESLint and the production build; add a test framework before claiming frontend automated coverage.
- Runtime or cross-layer changes: build and start the Compose stack, inspect health/logs, and browser-verify the affected journey.
- Readiness endpoints are currently static; a successful readiness response is not proof that PostgreSQL or Redis is healthy.

## Git and Delivery

- Inspect branch, remote, and worktree before every change.
- Existing worktree changes belong to the user. Preserve them and avoid staging or rewriting unrelated files.
- Keep changes scoped to the requested task.
- Build, test, run, and browser-verify through Docker Compose before committing or pushing.
- Do not commit or push until the user requests it or the current task explicitly includes delivery to GitHub.
