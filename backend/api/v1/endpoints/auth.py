from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import (
    blacklist_app_token,
    cache_user_profile,
    get_current_app_user,
)
from cache.dependencies import get_cache_helper
from cache.helpers import CacheHelper
from core.security import create_access_token
from db.dependencies import get_session
from models.user import User
from repositories.user import login_user
from repositories.auth_events import record_auth_event
from schemas.user import AuthorizedUserInternal, UserLogin, UserSchema

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

router = APIRouter(tags=["application-auth"])


@router.post("/login", response_model=AuthorizedUserInternal)
async def login_route(
    request: Request,
    credentials: UserLogin,
    session: AsyncSession = Depends(get_session),
    cache: CacheHelper = Depends(get_cache_helper),
) -> AuthorizedUserInternal:
    logged_in_user: User | None = await login_user(
        session,
        credentials.email,
        credentials.password,
    )
    if logged_in_user is None:
        await record_auth_event(
            session=session,
            event_type="signin_failure",
            request=request,
            email=credentials.email,
        )
        raise CREDENTIALS_EXCEPTION

    await cache_user_profile(logged_in_user, cache)
    token = create_access_token(subject=str(logged_in_user.id))
    await record_auth_event(
        session=session,
        event_type="signin_success",
        request=request,
        user_id=logged_in_user.id,
        token=token,
    )
    return AuthorizedUserInternal(
        id=str(logged_in_user.id),
        username=logged_in_user.email,
        is_admin=logged_in_user.is_admin,
        token=token,
    )


@router.api_route("/me", methods=["GET", "POST"], response_model=AuthorizedUserInternal)
async def read_me_route(
    current_user: UserSchema = Depends(get_current_app_user),
) -> AuthorizedUserInternal:
    return AuthorizedUserInternal(
        id=current_user.id,
        username=current_user.email,
        is_admin=current_user.is_admin,
        token=current_user.token,
    )


@router.get("/token-check")
async def token_check_route(
    current_user: UserSchema = Depends(get_current_app_user),
) -> dict[str, Any]:
    return {
        "message": f"Token is valid for user {current_user.email}",
        "status": True,
    }


@router.post("/logout")
async def logout_route(
    revoked: bool = Depends(blacklist_app_token),
) -> dict[str, str]:
    return {"message": "Successfully logged out"}


@router.post("/blacklist")
async def blacklist_route(
    revoked: bool = Depends(blacklist_app_token),
) -> dict[str, str]:
    return {"message": "Token blacklisted"}


@router.get("/is-admin")
async def is_admin_route(
    current_user: UserSchema = Depends(get_current_app_user),
) -> dict[str, bool]:
    return {"is_admin": current_user.is_admin}
