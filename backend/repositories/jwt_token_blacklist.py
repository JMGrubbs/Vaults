from sqlalchemy import select
from fastapi import Depends
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from models.jwt_token_blacklist import JwtTokenBlacklist
from cache.helpers import CacheHelper
from cache.dependencies import get_cache_helper


async def is_token_blacklisted_db(
    session: AsyncSession,
    jti: str,
    cache: CacheHelper,
) -> bool:
    blacklisted_token_in_cache = await cache.get_json(f"blacklisted_token:{jti}")
    if blacklisted_token_in_cache is not None:
        return True
    return False


async def load_recent_blacklisted_tokens(
    session: AsyncSession,
    minutes: int = 60,
    cache: CacheHelper = Depends(get_cache_helper),
) -> bool:
    cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
    result = await session.execute(
        select(JwtTokenBlacklist.token).where(JwtTokenBlacklist.blacklisted_at >= cutoff_time)
    )
    for row in result.fetchall():
        blacklisted_result = row[0]
        blacklisted_result = await cache.set_json(f"blacklisted_token:{blacklisted_result}", True, ttl=minutes * 60)

    return True


async def insert_blacklisted_token(session: AsyncSession, jti: str, cache: CacheHelper) -> bool:
    print(f"Inserting blacklisted token with jti: {jti}", flush=True)
    new_entry = JwtTokenBlacklist(token=jti, blacklisted_at=datetime.utcnow())
    session.add(new_entry)
    await session.commit()
    add_blacklisted_token_to_cache = await cache.set_json(f"blacklisted_token:{jti}", True, ttl=60 * 60)
    assert add_blacklisted_token_to_cache, "Failed to add blacklisted token to cache"
    return True