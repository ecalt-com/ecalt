from fastapi import APIRouter
from app.api.v1.endpoints import health, spark, explore, journeys, session

api_router = APIRouter()

api_router.include_router(health.router,   prefix="/health",   tags=["health"])
api_router.include_router(spark.router,    prefix="/spark",    tags=["spark"])
api_router.include_router(session.router,  prefix="/session",  tags=["session"])
api_router.include_router(explore.router,  prefix="/explore",  tags=["explore"])
api_router.include_router(journeys.router, prefix="/journeys", tags=["journeys"])
