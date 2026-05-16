import json
import logging
import time
import uuid
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.limiter import limiter
from app.api.v1.router import api_router

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    ms = round((time.perf_counter() - start) * 1000, 1)
    logging.info(json.dumps({
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": ms,
    }))
    response.headers["X-Request-Id"] = request_id
    return response

app.include_router(api_router, prefix="/api/v1")

# Vercel rewrite /sitemap.xml → /api/v1/sitemap
@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_redirect():
    from app.api.v1.endpoints.sitemap import sitemap
    return await sitemap()


@app.get("/", tags=["root"])
async def root():
    return {"service": "ecalt-api", "version": "0.1.0", "status": "running"}
