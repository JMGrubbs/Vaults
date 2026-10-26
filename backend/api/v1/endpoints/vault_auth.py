import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import (
    blacklist_vault_token,
    cache_user_profile,
    get_current_vault_user,
)
from cache.dependencies import get_cache_helper
from cache.helpers import CacheHelper
from core.config import settings
from core.security import create_access_token
from db.dependencies import get_session
from models.user import User
from repositories.user import login_user
from repositories.auth_events import record_auth_event
from schemas.user import AuthorizedUser, UserCreate, UserLogin, UserSchema
from services.user_registration import RegistrationConflict, register_user


CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication credentials",
)

router = APIRouter(tags=["vault-auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_route(
    request: Request,
    new_user: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str | uuid.UUID]:
    try:
        result = await register_user(session, new_user)
    except RegistrationConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if result.get("ok") is not True:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(result.get("message", "User registration failed")),
        )
    await record_auth_event(
        session=session,
        event_type="registration_success",
        request=request,
        user_id=result.get("user_id"),
        email=new_user.email,
    )
    return result


@router.post("/login", response_model=AuthorizedUser)
async def login_route(
    request: Request,
    response: Response,
    credentials: UserLogin,
    session: AsyncSession = Depends(get_session),
    cache: CacheHelper = Depends(get_cache_helper),
) -> AuthorizedUser:
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
    cookie_lifetime = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key=settings.cookie_key,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=cookie_lifetime,
        expires=cookie_lifetime,
        path="/",
    )
    return AuthorizedUser(username=logged_in_user.email)


@router.get("/me", response_model=AuthorizedUser)
async def read_me_route(
    current_user: UserSchema = Depends(get_current_vault_user),
) -> AuthorizedUser:
    return AuthorizedUser(username=current_user.email)


@router.get("/token-check")
async def token_check_route(
    current_user: UserSchema = Depends(get_current_vault_user),
) -> dict[str, Any]:
    return {
        "message": f"Token is valid for user {current_user.email}",
        "status": True,
    }


@router.post("/logout")
async def logout_route(
    response: Response,
    revoked: bool = Depends(blacklist_vault_token),
) -> dict[str, str]:
    response.delete_cookie(
        key=settings.cookie_key,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return {"message": "Successfully logged out"}


@router.get("/is-admin")
async def is_admin_route(
    current_user: UserSchema = Depends(get_current_vault_user),
) -> dict[str, bool]:
    return {"is_admin": current_user.is_admin}
