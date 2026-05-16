from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["root"])
async def root():
    return {"service": "ecalt-api", "version": "0.1.0", "status": "running"}
