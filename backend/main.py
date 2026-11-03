import json

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.v1.api import api_router
from cache.redis import redis_manager
from core.config import settings
from middleware.request_id import RequestIDMiddleware


def _cors_origins() -> list[str]:
    raw_origins = settings.cors_origins.strip()
    if not raw_origins:
        return []

    if raw_origins.startswith("["):
        try:
            parsed_origins = json.loads(raw_origins)
        except json.JSONDecodeError as exc:
            raise ValueError("CORS_ORIGINS must be CSV or a JSON array") from exc
        if not isinstance(parsed_origins, list) or not all(
            isinstance(origin, str) for origin in parsed_origins
        ):
            raise ValueError("CORS_ORIGINS JSON value must be an array of strings")
        origins = parsed_origins
    else:
        origins = raw_origins.split(",")

    normalized_origins = [origin.strip() for origin in origins if origin.strip()]
    if "*" in normalized_origins:
        raise ValueError("CORS_ORIGINS must contain explicit browser origins")
    return normalized_origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    yield
    await redis_manager.disconnect()


app = FastAPI(
    title="Auth Service",
    description="Central authentication and OAuth 2.1-style PKCE login service",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
