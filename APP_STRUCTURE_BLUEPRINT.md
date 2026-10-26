# Auth Service Application Structure Blueprint

This document maps the repository, service boundaries, active routes, data model,
and primary runtime flows for `auth-service`. It is the detailed contributor
reference for work spanning the React frontend, FastAPI API, PostgreSQL, Redis,
and Docker Compose.

This blueprint describes the current checkout. It distinguishes active behavior
from OAuth/PKCE scaffolding that is present but not wired into the application.

## Technology Summary

| Area | Technology |
| --- | --- |
| Frontend | React 19, Vite 8, JavaScript with JSX, React Router 7, Tailwind CSS 4, Axios |
| API | Python 3.14, FastAPI 0.135, Pydantic 2 |
| Authentication | PyJWT, HS256 by default, `pwdlib` password hashing |
| Persistence | PostgreSQL 17, SQLAlchemy 2 async sessions, Alembic |
| Cache | Redis 7.4 with the async Redis client |
| Local orchestration | Docker Compose |

## Repository Layout

```text
auth-service/
├── README.md
├── AGENTS.md
├── APP_STRUCTURE_BLUEPRINT.md
├── LICENSE
├── docker-compose.yaml
├── postgres/
│   └── init-db.sh
├── pyproject.toml
├── .env.example
├── backend/
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── api/v1/
│   │   ├── api.py
│   │   └── endpoints/
│   │       ├── auth.py
│   │       ├── health.py
│   │       └── users.py
│   ├── auth/
│   ├── cache/
│   ├── core/
│   ├── db/
│   ├── middleware/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── tests/
└── frontend/
    ├── .env.example
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── Dockerfile
    ├── public/
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── auth/
        ├── components/
        ├── layouts/
        ├── pages/
        └── services/
```

## Runtime Structure

```text
Browser
  |
  | http://localhost:5175
  v
React/Vite frontend :5173
  |
  | Axios to VITE_AUTH_SERVICE_BACKEND_URL
  | with browser credentials enabled
  v
FastAPI API :8000  <------ internal callers use a legacy token response
  |       |
  |       `------ Redis db-cache :6379
  |                 - revoked-token cache
  |                 - required during API startup
  |
  `-------------- PostgreSQL :5432
                    - auth.users
                    - auth.jwt_token_blacklist
                    - auth.alembic_version
```

Compose publishes the frontend on host port `5175`, the API on `8002`, and
PostgreSQL on `5434`. Redis is reachable only on the Compose network as
`db-cache`. Containers must use Compose service names rather than host
`localhost` addresses.

## Root Files

| Path | Purpose |
| --- | --- |
| `README.md` | Setup, runbook, authentication behavior, API snapshot, and limitations. |
| `AGENTS.md` | Repository-specific operating instructions and security guardrails. |
| `APP_STRUCTURE_BLUEPRINT.md` | This architecture and ownership map. |
| `docker-compose.yaml` | Defines services, ports, volumes, health checks, and startup ordering. |
| `postgres/init-db.sh` | Ensures the configured role, database, and owned `auth` schema exist when PostgreSQL initializes an empty data volume. |
| `.env.example` | Placeholder values used by Compose interpolation. |
| `pyproject.toml` | Minimal Python project metadata; dependencies remain in `backend/requirements.txt`. |

## Compose Services and Startup

| Service | Image/build | Published port | Volume or mount | Startup behavior |
| --- | --- | --- | --- | --- |
| `db-cache` | `redis:7.4-alpine` | None | `auth_redis_cache` | Disables snapshots and append-only persistence; health checked with `redis-cli ping`. |
| `postgres` | `postgres:17-alpine` | `5434:5432` | `postgres_data` plus the read-only initialization script | Initializes the configured role, database, and `auth` schema on a new data volume; health checked with `pg_isready`. |
| `postgres-init` | `postgres:17-alpine` | None | Read-only initialization script | Reconciles the application role from the backend `DATABASE_URL` after PostgreSQL is healthy, including for existing data volumes. |
| `api` | `backend/Dockerfile` | `8002:8000` | Bind mounts `./backend:/app` | Waits for PostgreSQL and Redis, runs Alembic, then starts reload-mode Uvicorn. |
| `frontend` | `frontend/Dockerfile` | `5175:5173` | Source bind mount plus `node_modules` volume | Starts the Vite development server after the API container starts. |

```text
postgres healthy ----> postgres-init completed ----+
db-cache healthy -----------------------------------+----> api started ----> frontend started
```

The API lifespan opens a shared Redis connection and verifies it with `PING`.
Failure to connect prevents API startup. Migrations run before Uvicorn, but the
health and readiness routes do not query PostgreSQL or Redis.

The PostgreSQL image processes `postgres/init-db.sh` while initializing an
empty data directory. Compose also runs it through a one-shot `postgres-init`
service on every startup so existing volumes are reconciled before the API
starts. That service derives the application role, password, and database from
the backend `DATABASE_URL`; the script quotes configured identifiers and makes
the application role the owner of the database and `auth` schema. Alembic also
retains its defensive `CREATE SCHEMA IF NOT EXISTS auth` behavior.

## Backend API

`backend/main.py` creates the FastAPI application, owns the Redis lifespan, installs
request-ID and CORS middleware, and mounts the v1 router at `/api/v1`.

### Backend directories

| Path | Responsibility |
| --- | --- |
| `backend/api/v1/endpoints/` | Separate Vault browser auth, application auth, user administration, and health handlers. |
| `backend/auth/` | Resolves cookie or custom-header users, caches active profiles, and revokes tokens. |
| `backend/cache/` | Redis lifecycle, dependency injection, and JSON helpers. |
| `backend/core/` | Pydantic settings plus JWT/password primitives. |
| `backend/db/` | Async SQLAlchemy engine, sessions, dependency, and metadata. |
| `backend/middleware/` | Request-ID middleware; the other modules are empty placeholders. |
| `backend/models/` | SQLAlchemy models in the PostgreSQL `auth` schema. |
| `backend/repositories/` | User persistence, token-revocation persistence/cache operations, and authentication-event audit writes. |
| `backend/schemas/` | Pydantic request, response, and internal user shapes. |
| `backend/services/` | Registration plus unmounted authorization-code/rate-limit scaffolding. |
| `backend/alembic/` | Async migration environment and schema history. |
| `backend/tests/` | Python `unittest` regression tests. |

### Active routes

Every route below is prefixed with `/api/v1`.

| Method | Route | Handler | Authentication | Purpose |
| --- | --- | --- | --- | --- |
| `GET` | `/health` | `health_check` | None | Returns a basic process status. |
| `GET` | `/health/ready` | `readiness_check` | None | Returns a static ready status. |
| `GET` | `/health/live` | `liveness_check` | None | Returns alive status and a UTC timestamp. |
| `POST` | `/vault/auth/register` | `register_route` | None | Registers a normalized email/password account for Vault. |
| `POST` | `/vault/auth/login` | `login_route` | Credentials in body | Issues the Vault browser cookie and returns the username. |
| `GET` | `/vault/auth/me` | `read_me_route` | Cookie | Returns the active Vault user. |
| `GET` | `/vault/auth/token-check` | `token_check_route` | Cookie | Confirms the Vault session is valid. |
| `POST` | `/vault/auth/logout` | `logout_route` | Cookie | Blacklists the token `jti` and deletes the cookie. |
| `GET` | `/vault/auth/is-admin` | `is_admin_route` | Cookie | Returns the Vault user's admin flag. |
| `POST` | `/auth/login` | `login_route` | Credentials in body | Returns the legacy application token response. |
| `GET`, `POST` | `/auth/me` | `read_me_route` | `token` or `Authorization: Bearer` header | Returns the application response, including the same token. |
| `GET` | `/auth/token-check` | `token_check_route` | `token` or `Authorization: Bearer` header | Confirms the application token is valid. |
| `POST` | `/auth/logout` | `logout_route` | `token` or `Authorization: Bearer` header | Blacklists the application token `jti`; safe to retry. |
| `POST` | `/auth/blacklist` | `blacklist_route` | `token` or `Authorization: Bearer` header | Explicitly blacklists the application token `jti`; safe to retry. |
| `GET` | `/auth/is-admin` | `is_admin_route` | `token` or `Authorization: Bearer` header | Returns the application user's admin flag. |
| `POST` | `/users/create` | `create_new_user_route` | None | Registers a normalized email/password account. |
| `DELETE` | `/users/delete` | `delete_user_route` | Current user; inline admin check | Deletes a target user by email. |
| `POST` | `/users/deactivate` | `deactivate_user_route` | Cookie | Marks the current user inactive. |
| `POST` | `/users/make-admin` | `make_admin_route` | Current user; inline admin check | Grants admin status to a target user. |

No `/oauth` router is included by `backend/api/v1/api.py`.

## Authentication and Revocation Flows

### Browser login

```text
Login page
  |
  | POST /api/v1/vault/auth/login { email, password }
  v
login_route
  |
  | active-user lookup + password verification
  v
JWT { sub, exp, iat, jti }
  |
  +--> Set COOKIE_KEY cookie
  |    HttpOnly; Secure; SameSite=Lax; Path=/; one hour
  |
  `--> Return { username }
```

Axios uses `withCredentials: true`, so browser API calls include the cookie when
the browser's origin and cookie rules permit it.

### Internal login

```text
Internal caller
  |
  | POST /api/v1/auth/login
  | { email, password }
  v
Auth Service
  |
  `--> { id, username, is_admin, token }
```

This is the preserved direct-token application response. Its companion profile call is
`GET` or `POST /api/v1/auth/me` with the token in the legacy `token` header or a
standard `Authorization: Bearer ...` header.

### Authenticated request and logout

```text
Vault cookie or application custom header
  |
  v
decode JWT and read jti/exp
  |
  +--> Redis blacklisted_token:<jti> exists? --> 401
  |
  `--> Redis auth:user:<sub> cached profile?
       +--> cache hit --> route handler
       `--> load active user from PostgreSQL, cache 5 minutes --> route handler

POST /api/v1/vault/auth/logout with cookie
  |
  +--> insert jti in auth.jwt_token_blacklist
  +--> cache blacklisted_token:<jti> in Redis for one hour
  `--> delete the Vault session cookie
```

The revocation check reads Redis only. PostgreSQL is the durable record, and
`load_recent_blacklisted_tokens()` can repopulate Redis, but no startup hook
currently calls it.

Each sign-in and authenticated request also writes an audit event to
`auth.auth_events`. Token-use events occur after Redis revocation and profile
checks succeed, so a recorded use represents an accepted authenticated request.

## User Validation

`UserCreate` trims and lowercases email addresses. New passwords require at
least eight characters, one letter, one digit, and one configured special
character. Passwords are hashed with `PasswordHash.recommended()`.

`UserLogin` also normalizes email. Login and current-user repository queries
only return active users.

## Persistence

All application-owned tables and the Alembic version table live in the
PostgreSQL `auth` schema.

### `auth.users`

| Column | Purpose |
| --- | --- |
| `id` | UUID primary key generated by the application. |
| `email` | Unique, indexed account identifier. |
| `hashed_password` | Password hash; plaintext passwords must never be stored. |
| `is_active` | Controls whether repository lookups can authenticate the user. |
| `is_admin` | Controls handler-level administration checks. |

### `auth.jwt_token_blacklist`

| Column | Purpose |
| --- | --- |
| `id` | Integer primary key. |
| `token` | Unique, indexed JWT ID (`jti`), not the full JWT. |
| `blacklisted_at` | Revocation timestamp. |

### `auth.auth_events`

| Column | Purpose |
| --- | --- |
| `id` | UUID event identifier. |
| `event_type` | `signin_success`, `signin_failure`, `token_use`, `logout`, or `registration_success`. |
| `user_id` | Optional UUID for events associated with a known account. |
| `occurred_at` | UTC event timestamp. |
| `request_id` | Correlation ID from request middleware. |
| `token_fingerprint` | SHA-256 fingerprint of a token; raw JWTs are never stored. |
| `email_fingerprint` | SHA-256 fingerprint used to correlate failed sign-ins without storing email text. |
| `ip_address`, `user_agent`, `method`, `path` | Request context for audit and investigation. |

The migrations create the schema and all three application tables. Compose runs
`alembic upgrade head` on every API container start.

## Frontend

The frontend is a React single-page application. `main.jsx` mounts a
`BrowserRouter`, wraps the application in `AuthProvider`, and imports Tailwind
styles. API calls use an Axios instance whose base URL comes from
`VITE_AUTH_SERVICE_BACKEND_URL`.

### Frontend files

| Path | Purpose |
| --- | --- |
| `frontend/src/main.jsx` | React entry point, router, and authentication provider wiring. |
| `frontend/src/App.jsx` | Top navigation and route definitions. |
| `frontend/src/auth/AuthProvider.jsx` | Loads the user, runs auth calls, and handles 401 events. |
| `frontend/src/components/ProtectedRoute.jsx` | Guards authenticated routes and optional permissions. |
| `frontend/src/layouts/` | Outlet-only route layouts. |
| `frontend/src/pages/Login.jsx` | Credential login form. |
| `frontend/src/pages/Register.jsx` | Registration and password-confirmation form. |
| `frontend/src/pages/UserPage.jsx` | Account profile with live email plus placeholder fields. |
| `frontend/src/pages/AppManagment.jsx` | Searchable connected-app mockup with non-persisted controls. |
| `frontend/src/pages/About.jsx` | Public Vaults product overview. |
| `frontend/src/services/api.jsx` | Credentialed Axios client and session-expiration event. |
| `frontend/src/services/AuthService.jsx` | Login, registration, and logout requests. |
| `frontend/src/services/User.jsx` | Current-user request. |
| `frontend/vite.config.js` | React/Tailwind plugins, port, host binding, and allowed host. |

### Registered frontend routes

| Route | Page | Access |
| --- | --- | --- |
| `/auth/login` | `Login.jsx` | Public; redirects authenticated users. |
| `/auth/register` | `Register.jsx` | Public; redirects authenticated users. |
| `/user` | `UserPage.jsx` | Protected. |
| `/apps` | `AppManagment.jsx` | Protected; content is mock data. |
| `/home` | `Home.jsx` | Public in the router. |
| `/about` | `About.jsx` | Public. |
| `/unauthorized` | `Unauthorized.jsx` | Public. |
| Any other path | Redirect | Redirects to `/about`. |

`NotFound.jsx` exists but is not mounted. Login, registration, protected-route,
and expired-session navigation use the registered `/auth/*` browser routes.

## Configuration Boundaries

| File | Important settings |
| --- | --- |
| Root `.env` | PostgreSQL bootstrap credentials, application-role defaults, and Compose-level OAuth placeholders. |
| `backend/.env` | Database/Redis URLs, signing secret, algorithm, token lifetime, cookie name, exact CORS origins, and OAuth placeholders. |
| `frontend/.env` | Browser-visible API base URL in `VITE_AUTH_SERVICE_BACKEND_URL`. |

Environment files are ignored and must not be read, logged, or committed.
Tracked examples contain placeholders only.

The tracked root, backend, and frontend examples cover the variables currently
read by Compose and application settings. The root `POSTGRES_APP_*` values must
remain synchronized with the corresponding credentials and database in the
backend `DATABASE_URL` when local files are created.

Important current details:

- CORS reads the comma-separated `CORS_ORIGINS` setting and enables credentials
  only for those exact origins.
- OAuth client, timeout, and rate-limit settings have no active route consumers.

## OAuth/PKCE Scaffolding Status

`backend/services/authorization_codes.py` defines opaque code issuance and atomic
single-use consumption through Redis `GETDEL`. Its grants bind a user, client
ID, redirect URI, and PKCE challenge. The module calls
`core.oauth.verify_pkce`, but `backend/core/oauth.py` is not present.

`backend/services/login_rate_limit.py` defines Redis-backed IP and normalized-email
buckets with hashed identifiers. Nothing currently instantiates or calls it.

The settings and Compose file include authorization-code expiry and login-rate
variables. No route parses registered clients, validates redirect
URIs, accepts `state`, issues codes, or exchanges a code for a token. These
modules are foundations for future work, not an active OAuth contract.

## Middleware and Observability

`RequestIDMiddleware` assigns a UUID to every request and returns it in the
`X-Request-ID` response header. It does not honor an incoming request ID or add
the value to structured logs.

CORS currently allows all origins, methods, and headers while also enabling
credentials. Production work should replace this with an environment-derived
explicit origin list and browser verification.

`backend/middleware/auth.py`, `cors.py`, and `logging.py` are empty placeholders.

## Tests and Development Commands

Run from the repository root:

```bash
# Validate Compose without printing resolved configuration
docker compose config --quiet

# Build and start the stack
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 120 api frontend

# Run API unit tests
docker compose run --rm --no-deps api \
  python -m unittest discover -s tests -p 'test_*.py'

# Check frontend source and production bundling
docker compose run --rm --no-deps frontend npm run lint
docker compose run --rm --no-deps frontend npm run build
```

The API suite covers route separation, browser-cookie and application-token
login behavior, Redis user caching, Dockerfile package transport configuration,
and token logging. There is no frontend test script or Compose test profile;
the repository-level contract test prevents browser services from calling the
application-token namespace.

## Current Gaps and Extension Points

- Complete or remove the unfinished OAuth/PKCE surface. A completed flow needs
  registered-client parsing, exact redirect matching, required `state`, PKCE
  `S256`, one-time code routes, integration tests, and a working client flow.
- Replace wildcard CORS with explicit environment-driven origins.
- Decide whether to migrate internal callers from the custom `token` header to
  standard bearer authentication; preserve compatibility during a transition.
- Make readiness probe PostgreSQL and Redis instead of returning a constant.
- Restore durable revocations from PostgreSQL into Redis during startup, or
  document a different cache-recovery strategy.
- Replace connected-app, permissions, activity, and profile placeholders with
  persisted models and APIs before presenting them as account state.
- Add endpoint/service tests, frontend component tests, and browser-level auth
  coverage.
- Keep all three `.env.example` files synchronized as runtime settings evolve.
