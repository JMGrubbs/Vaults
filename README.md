# Auth Service

A centralized FastAPI identity API with a React/Vite account portal branded as Vaults. The service owns users, password verification, JWT issuance, cookie authentication, token revocation, and basic account administration.

The current application implements direct credential login. OAuth 2.1-style authorization-code and rate-limit service modules are present, but they are not connected to HTTP routes yet. There are no `/api/v1/oauth/*` endpoints or browser PKCE helper in this checkout.

For a detailed repository and runtime map, see [`APP_STRUCTURE_BLUEPRINT.md`](APP_STRUCTURE_BLUEPRINT.md).

## Architecture

- **Frontend:** React 19, JavaScript/JSX, Vite 8, React Router 7, Tailwind CSS 4, and Axios.
- **API:** Python 3.14 and FastAPI on container port `8000`.
- **Database:** PostgreSQL 17 with SQLAlchemy 2 and Alembic.
- **Cache:** Redis 7.4 for the revoked-token cache.
- **Authentication:** HS256 JWTs, `pwdlib` password hashing, and an HttpOnly browser cookie.
- **Runtime:** Docker Compose publishes the frontend on `5175`, API on `8002`, and PostgreSQL on `5434`.

The browser calls the API URL configured by `VITE_AUTH_SERVICE_BACKEND_URL` with credentials enabled. CORS is currently hard-coded to `*` in `backend/main.py`; no environment-backed CORS setting is wired into the middleware.

## Configure

Prerequisites: Docker Engine and Docker Compose v2.

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Replace both database-password placeholders in the root environment file. Keep
`POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD`, and `POSTGRES_APP_DB` synchronized
with the username, password, and database in the backend `DATABASE_URL`. Replace
the signing-secret placeholder before using the service outside local
development. The frontend template points to the locally published API at
`http://localhost:8002`.

The tracked examples contain OAuth timeout and rate-limit placeholders reserved for the unfinished authorization-code flow; no active route consumes them. Values prefixed with `VITE_` are public and must never contain secrets.

On the first startup of an empty PostgreSQL data volume, Compose mounts
`postgres/init-db.sh` into the image initialization directory. The script
ensures the configured database role and database exist, creates the `auth`
schema, and assigns ownership to that role. PostgreSQL initialization scripts
do not run again for an existing data volume.

Compose also runs the script through the one-shot `postgres-init` service on
every startup. That service reads the application role, password, and database
from the backend `DATABASE_URL`, reconciles the role password, and must finish
successfully before the API runs migrations. This keeps existing data volumes
compatible when application database credentials change.

## Run

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

- Vaults frontend: <http://localhost:5175>
- API docs: <http://localhost:8002/docs>
- Health: <http://localhost:8002/api/v1/health>
- PostgreSQL: `localhost:5434`

Stop without deleting data:

```bash
docker compose down
```

`docker compose down -v` is destructive and removes database/cache volumes.

## Authentication Behavior

Browser login sends an email and password to `POST /api/v1/auth/login`. A successful non-internal login returns the username and sets a JWT in the cookie named by `COOKIE_KEY`. The cookie is `HttpOnly`, `Secure`, `SameSite=Lax`, and has a one-hour lifetime.

Internal callers can send `"internal": true` in the same request and receive the user ID, username, admin flag, and token in the JSON response. This is a legacy compatibility contract, not an OAuth token exchange. `POST /api/v1/auth/me` accepts the token through the custom `token` header; browser `GET /api/v1/auth/me` reads the cookie.

Logout stores the JWT ID (`jti`) in PostgreSQL and Redis. Subsequent authenticated requests reject a cached revoked token.

## API Snapshot

All application routes are mounted below `/api/v1`.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health`, `/health/ready`, `/health/live` | Process status; readiness is currently a static response. |
| `POST` | `/auth/login` | Validate credentials and set a cookie or return the internal token response. |
| `GET`, `POST` | `/auth/me` | Return the current active user from a cookie or legacy `token` header. |
| `GET` | `/auth/token-check` | Confirm that the current cookie token is valid. |
| `POST` | `/auth/logout` | Revoke the current cookie token. |
| `GET` | `/auth/is-admin` | Return the current user's admin flag. |
| `POST` | `/users/create` | Register a user after password validation and hashing. |
| `DELETE` | `/users/delete` | Delete a user by email after the handler's admin check. |
| `POST` | `/users/deactivate` | Mark the current user inactive. |
| `POST` | `/users/make-admin` | Grant admin status after the handler's admin check. |

FastAPI exposes the generated request and response schemas at `/docs`.

## Tests

```bash
docker compose run --rm --no-deps api python -m unittest discover -s tests -p 'test_*.py'
docker compose run --rm --no-deps frontend npm run lint
docker compose run --rm --no-deps frontend npm run build
```

The frontend does not currently have an automated test script or a Compose test profile.

## Current Limitations

- `backend/services/authorization_codes.py` and `backend/services/login_rate_limit.py` are scaffolding only. They are not mounted by `backend/api/v1/api.py`, and the authorization-code module imports a missing `core.oauth` module.
- OAuth client, expiry, and login-rate configuration is not used by an active flow.
- The current frontend auth flow needs repair: its provider references undefined OAuth values, async form actions are not consistently awaited, and some `/user/*` redirects do not match the registered `/auth/*` routes.
- Connected-app and profile-management screens contain placeholder data and disabled controls.
- Readiness does not probe PostgreSQL or Redis, and logout does not explicitly delete the browser cookie.

These are implementation notes, not supported integration contracts. Add behavioral tests before changing or completing the flows.
