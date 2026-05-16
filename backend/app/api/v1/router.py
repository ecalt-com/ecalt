from fastapi import APIRouter
from app.api.v1.endpoints import health, explore, journeys

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(explore.router, prefix="/explore", tags=["explore"])
api_router.include_router(journeys.router, prefix="/journeys", tags=["journeys"])
