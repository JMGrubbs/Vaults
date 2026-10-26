from fastapi import APIRouter

from api.v1.endpoints import auth, health, users, vault_auth


api_router = APIRouter()
api_router.include_router(vault_auth.router, prefix="/vault/auth")
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
