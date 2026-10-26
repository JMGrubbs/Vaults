from redis.asyncio import Redis
from fastapi import Depends

from cache.redis import redis_manager
from cache.helpers import CacheHelper


def get_redis() -> Redis:
    """
    FastAPI dependency for accessing the shared async Redis client.
    """
    return redis_manager.get_client()


def get_cache_helper(redis: Redis = Depends(get_redis)) -> CacheHelper:
    """
    FastAPI dependency for accessing the CacheHelper, which provides
    convenient methods for working with Redis.
    """
    return CacheHelper(redis)
