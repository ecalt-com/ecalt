import logging
import time
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging_config import setup_logging
from app.core.impersonation_audit import ImpersonationAuditMiddleware
from app.api.v1.router import api_router

# Called once at module load — may be overwritten by uvicorn's dictConfig
setup_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)
    if settings.ENVIRONMENT != "development" and not settings.NOTIFICATION_SIGNING_SECRET:
        raise RuntimeError("NOTIFICATION_SIGNING_SECRET must be set in production")
    from app.core.database import _get_pool, warm_pool
    try:
        _get_pool()
        warm_pool()
    except Exception:
        pass  # logged inside; don't prevent startup
    from app.services.scheduler import setup_scheduler
    sched = setup_scheduler()
    sched.start()
    yield
    sched.shutdown(wait=False)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
    )

_DESCRIPTION = """
## ECALT — Curiosity Engine API

Turn any question into a guided, step-by-step learning journey powered by Claude AI.

### Endpoints

| Tag | Purpose |
|-----|---------|
| **explore** | Generate an AI-curated Journey from a free-form question |
| **journeys** | Browse and retrieve pre-built and AI-generated journeys |
| **health** | Service liveness check |

### Journey structure

A **Journey** contains an ordered list of **JourneySteps**, each typed as one of:
`concept` · `practice` · `challenge` · `explore`

Age groups: `kids` · `teens` · `adults` · `all`
Difficulty levels: `beginner` · `intermediate` · `advanced`
"""

_TAGS_METADATA = [
    {
        "name": "explore",
        "description": "Submit a curiosity question and receive a structured AI-generated Journey.",
    },
    {
        "name": "journeys",
        "description": "List all available journeys or fetch a single journey by ID.",
    },
    {
        "name": "health",
        "description": "Liveness probe — returns service status and UTC timestamp.",
    },
    {
        "name": "root",
        "description": "Root endpoint — service identity and version.",
    },
]

app = FastAPI(
    lifespan=lifespan,
    title="ECALT API",
    description=_DESCRIPTION,
    version="0.1.0",
    contact={"name": "ECALT Team", "email": "developer.biswambar@gmail.com"},
    openapi_tags=_TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_log = logging.getLogger("ecalt.unhandled")


@app.exception_handler(HTTPException)
async def http_exception_log_handler(request: Request, exc: HTTPException):
    """Log all HTTPExceptions with their detail so 4xx/5xx are visible in logs."""
    ctx = {
        "path":   request.url.path,
        "method": request.method,
        "status": exc.status_code,
        "detail": exc.detail,
    }
    if exc.status_code >= 500:
        # exc_info=True prints the chained traceback (e.g. the original
        # Razorpay / Stripe error that was wrapped into the HTTPException).
        _log.error("http_error", exc_info=True, extra=ctx)
    elif exc.status_code >= 400:
        _log.warning("http_error", extra=ctx)
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all so unhandled exceptions return a proper JSON 500 and CORS
    headers are still present (Starlette's ServerErrorMiddleware returns a
    plain response that bypasses CORSMiddleware)."""
    _log.exception(
        "Unhandled exception",
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ImpersonationAuditMiddleware)

_req_log = logging.getLogger("ecalt.request")


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.perf_counter()

    response = await call_next(request)

    ms = round((time.perf_counter() - start) * 1000, 1)
    ctx = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": ms,
    }
    if response.status_code >= 500:
        _req_log.error("server error", extra=ctx)
    elif response.status_code >= 400:
        _req_log.warning("client error", extra=ctx)
    else:
        _req_log.info("ok", extra=ctx)

    response.headers["X-Request-Id"] = request_id
    return response


app.include_router(api_router, prefix="/api/v1")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_redirect():
    from app.api.v1.endpoints.sitemap import sitemap
    return await sitemap()


@app.get("/", tags=["root"])
async def root():
    return {"service": "ecalt-api", "version": "0.1.0", "status": "running"}
