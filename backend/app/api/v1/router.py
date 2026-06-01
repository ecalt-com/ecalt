from fastapi import APIRouter
from app.api.v1.endpoints import (
    health, spark, explore, journeys, session, users, progress, passport, sitemap,
    chat, knowledge, subscriptions, admin, mind_signature, coupons, notifications, geo, quiz,
)

api_router = APIRouter()

api_router.include_router(health.router,        prefix="/health",        tags=["health"])
api_router.include_router(spark.router,         prefix="/spark",         tags=["spark"])
api_router.include_router(session.router,       prefix="/session",       tags=["session"])
api_router.include_router(explore.router,       prefix="/explore",       tags=["explore"])
api_router.include_router(journeys.router,      prefix="/journeys",      tags=["journeys"])
api_router.include_router(users.router,         prefix="/users",         tags=["users"])
api_router.include_router(progress.router,      prefix="/progress",      tags=["progress"])
api_router.include_router(passport.router,      prefix="/passport",      tags=["passport"])
api_router.include_router(sitemap.router,       prefix="/sitemap",       tags=["sitemap"])
api_router.include_router(chat.router,          prefix="/chat",          tags=["chat"])
api_router.include_router(knowledge.router,     prefix="/knowledge",     tags=["knowledge"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(admin.router,         prefix="/admin",         tags=["admin"])
api_router.include_router(mind_signature.router, prefix="/mind-signature", tags=["mind-signature"])
api_router.include_router(coupons.router,       prefix="/coupons",        tags=["coupons"])
api_router.include_router(notifications.router, prefix="/notifications",  tags=["notifications"])
api_router.include_router(geo.router,           prefix="/geo",            tags=["geo"])
api_router.include_router(quiz.router,          prefix="/quiz",           tags=["quiz"])
