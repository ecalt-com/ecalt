"""Public, non-secret settings the web app needs to render correctly."""
from fastapi import APIRouter, Response

from app.core.config import settings
from app.services.language_service import LANGUAGES

router = APIRouter()


@router.get("/public", summary="Feature settings the web app reads at start-up")
def public_config(response: Response):
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "quiz_gate_mode": "optional" if settings.QUIZ_GATE_MODE == "optional" else "required",
        "languages": [{"code": code, "name": name} for code, name in LANGUAGES.items()],
    }
