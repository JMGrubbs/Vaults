from __future__ import annotations

import hashlib
import uuid
from typing import Literal

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from models.auth_event import AuthEvent


AuthEventType = Literal[
    "signin_success",
    "signin_failure",
    "token_use",
    "logout",
    "registration_success",
]


def fingerprint(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def record_auth_event(
    *,
    session: AsyncSession,
    event_type: AuthEventType,
    request: Request,
    user_id: uuid.UUID | str | None = None,
    token: str | None = None,
    email: str | None = None,
) -> AuthEvent:
    client = request.client
    event = AuthEvent(
        event_type=event_type,
        user_id=uuid.UUID(str(user_id)) if user_id is not None else None,
        request_id=getattr(request.state, "request_id", None),
        token_fingerprint=fingerprint(token),
        email_fingerprint=fingerprint(email.strip().lower() if email else None),
        ip_address=client.host if client is not None else None,
        user_agent=request.headers.get("user-agent"),
        method=request.method,
        path=request.url.path,
    )
    session.add(event)
    await session.commit()
    return event
