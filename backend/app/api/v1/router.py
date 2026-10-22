from fastapi import APIRouter, Depends
from app.api.v1.endpoints import (
    health, spark, explore, journeys, session, users, progress, passport, sitemap,
    chat, knowledge, subscriptions, admin, mind_signature, coupons, notifications, geo, quiz,
    family, schools, admin_schools, school_roster, school_login, school_documents,
)
from app.core.school_auth import require_schools_enabled

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
api_router.include_router(family.router,        prefix="/family",         tags=["family"])

# Schools (plans/school-courses) — 404 while SCHOOLS_ENABLED is off.
_schools_flag = [Depends(require_schools_enabled)]
api_router.include_router(schools.router,         prefix="/schools",        tags=["schools"], dependencies=_schools_flag)
api_router.include_router(school_roster.router,   prefix="/schools",        tags=["schools"], dependencies=_schools_flag)
api_router.include_router(school_documents.router, prefix="/schools",        tags=["schools"], dependencies=_schools_flag)
api_router.include_router(school_login.router,    prefix="/school-login",   tags=["schools"], dependencies=_schools_flag)
api_router.include_router(schools.invites_router, prefix="/school-invites", tags=["schools"], dependencies=_schools_flag)
api_router.include_router(admin_schools.router,   prefix="/admin/schools",  tags=["schools"], dependencies=_schools_flag)
