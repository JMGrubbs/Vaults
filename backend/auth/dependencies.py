from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from cache.dependencies import get_cache_helper
from cache.helpers import CacheHelper
from core.config import settings
from core.security import decode_access_token
from db.dependencies import get_session
from models.user import User
from repositories.jwt_token_blacklist import (
    insert_blacklisted_token,
    is_token_blacklisted_db,
)
from repositories.user import get_user_by_id
from repositories.auth_events import record_auth_event
from schemas.user import UserSchema


USER_CACHE_TTL_SECONDS = 300

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def _user_cache_key(user_id: str) -> str:
    return f"auth:user:{user_id}"


def extract_app_token(request: Request) -> str | None:
    legacy_token = request.headers.get("token")
    if legacy_token:
        return legacy_token.strip() or None

    authorization = request.headers.get("authorization", "")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()
    return None


async def cache_user_profile(user: User | UserSchema, cache: CacheHelper) -> UserSchema:
    user_schema = UserSchema(
        id=str(user.id),
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
    )
    await cache.set_json(
        _user_cache_key(user_schema.id),
        user_schema.model_dump(mode="json", exclude={"token"}),
        ttl=USER_CACHE_TTL_SECONDS,
    )
    return user_schema


async def invalidate_user_profile(user_id: str, cache: CacheHelper) -> None:
    await cache.delete_json(_user_cache_key(user_id))


async def get_cached_user(
    user_id: str,
    session: AsyncSession,
    cache: CacheHelper,
) -> UserSchema | None:
    cache_key = _user_cache_key(user_id)
    cached_user = await cache.get_json(cache_key)
    if cached_user is not None:
        try:
            return UserSchema.model_validate(cached_user)
        except ValidationError:
            await cache.delete_json(cache_key)

    user = await get_user_by_id(session, user_id)
    if user is None:
        return None
    return await cache_user_profile(user, cache)


def _decode_valid_token(token: str) -> dict[str, Any]:
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise CREDENTIALS_EXCEPTION from exc

    token_jti = payload.get("jti")
    expiration = int(payload.get("exp", 0))
    if not token_jti or expiration <= int(datetime.now(timezone.utc).timestamp()):
        raise CREDENTIALS_EXCEPTION
    return payload


async def check_token_blacklist(
    token: str,
    session: AsyncSession,
    cache: CacheHelper,
) -> bool:
    payload = _decode_valid_token(token)
    return await is_token_blacklisted_db(
        session=session,
        jti=str(payload["jti"]),
        cache=cache,
    )


async def _resolve_current_user(
    token: str | None,
    session: AsyncSession,
    cache: CacheHelper,
    request: Request,
) -> UserSchema:
    if not token:
        raise CREDENTIALS_EXCEPTION

    payload = _decode_valid_token(token)
    if await is_token_blacklisted_db(
        session=session,
        jti=str(payload["jti"]),
        cache=cache,
    ):
        raise CREDENTIALS_EXCEPTION

    subject = payload.get("sub")
    if subject is None:
        raise CREDENTIALS_EXCEPTION

    user = await get_cached_user(str(subject), session, cache)
    if user is None or not user.is_active:
        raise CREDENTIALS_EXCEPTION
    await record_auth_event(
        session=session,
        event_type="token_use",
        request=request,
        user_id=user.id,
        token=token,
    )
    return user.model_copy(update={"token": token})


async def get_current_vault_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    cache: CacheHelper = Depends(get_cache_helper),
) -> UserSchema:
    return await _resolve_current_user(
        request.cookies.get(settings.cookie_key),
        session,
        cache,
        request,
    )


async def get_current_app_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    cache: CacheHelper = Depends(get_cache_helper),
) -> UserSchema:
    return await _resolve_current_user(extract_app_token(request), session, cache, request)


# Existing account-administration routes remain cookie-authenticated.
get_current_user = get_current_vault_user


async def require_admin(
    current_user: UserSchema = Depends(get_current_vault_user),
) -> UserSchema:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    return current_user


async def _revoke_token(
    token: str | None,
    session: AsyncSession,
    cache: CacheHelper,
    request: Request,
) -> bool:
    if not token:
        raise CREDENTIALS_EXCEPTION

    payload = _decode_valid_token(token)
    revoked = bool(
        await insert_blacklisted_token(session=session, jti=str(payload["jti"]), cache=cache)
    )
    await record_auth_event(
        session=session,
        event_type="logout",
        request=request,
        user_id=payload.get("sub"),
        token=token,
    )
    return revoked


async def blacklist_vault_token(
    request: Request,
    session: AsyncSession = Depends(get_session),
    cache: CacheHelper = Depends(get_cache_helper),
) -> bool:
    return await _revoke_token(
        request.cookies.get(settings.cookie_key),
        session,
        cache,
        request,
    )


async def blacklist_app_token(
    request: Request,
    session: AsyncSession = Depends(get_session),
    cache: CacheHelper = Depends(get_cache_helper),
) -> bool:
    return await _revoke_token(extract_app_token(request), session, cache, request)


blacklist_current_token = blacklist_vault_token
