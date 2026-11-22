"""Learning in your language (F2.2): Hindi first.

The language a model call should write in travels in a ContextVar, set around the
generation with use_language(), and provider_service.complete_text appends one
instruction to the system prompt for the interaction types that write to learners.
That avoids threading a parameter through every prompt builder. Anything that
asks for JSON keeps its keys and enum values in English.

Every lookup falls back to English on any error, and nothing here references the
new columns for English content, so the code is safe to deploy before the migration.
"""
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from app.core.database import get_db

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGE = "en"
LANGUAGES: dict[str, str] = {"en": "English", "hi": "Hindi"}   # add a code here to support another language

# Interaction types that write text to learners. Critics, planners, extraction and
# fingerprinting stay in English: their output isn't shown to anyone.
LANGUAGE_AWARE_TYPES = frozenset({
    "journey", "step_content", "quiz", "journey_tutor", "daily_chat", "onboarding", "spark", "daily_spark",
})

_current: ContextVar[str] = ContextVar("content_language", default=DEFAULT_LANGUAGE)


def normalize(code: Optional[str]) -> str:
    code = (code or "").strip().lower()
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def current() -> str:
    return _current.get()


@contextmanager
def use_language(code: Optional[str]) -> Iterator[str]:
    token = _current.set(normalize(code))
    try:
        yield _current.get()
    finally:
        _current.reset(token)


def instruction(code: str) -> str:
    name = LANGUAGES.get(code)
    if not name or code == DEFAULT_LANGUAGE:
        return ""
    return (
        f"LANGUAGE: Write every sentence a learner will read in {name}: clear, natural, "
        f"age-appropriate {name}" + (" in Devanagari script" if code == "hi" else "") + ". "
        "Keep JSON keys, ids, step types, difficulty levels and any other fixed values exactly as "
        "specified in English. A technical term may stay in English in brackets after its "
        f"{name} translation."
    )


def apply(system: str, interaction_type: Optional[str]) -> str:
    """The system prompt with the current language's instruction, for learner-facing types."""
    code = current()
    if code == DEFAULT_LANGUAGE or interaction_type not in LANGUAGE_AWARE_TYPES:
        return system
    return f"{system}\n\n{instruction(code)}"


def _one(sql: str, params: tuple) -> Optional[str]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return row["language"] if row else None
    except Exception:
        logger.debug("language lookup failed", exc_info=True)
        return None


def user_language(uid: Optional[str]) -> str:
    if not uid:
        return DEFAULT_LANGUAGE
    return normalize(_one("SELECT preferred_language AS language FROM users WHERE uid = %s", (uid,)))


def journey_language(journey_id: Optional[str]) -> str:
    if not journey_id:
        return DEFAULT_LANGUAGE
    return normalize(_one("SELECT language FROM journeys WHERE id = %s", (journey_id,)))


def quiz_language(quiz_id: str, uid: str) -> str:
    """The language a quiz question was written in: its journey's, else the learner's."""
    code = _one("SELECT j.language FROM quiz_sessions s JOIN journeys j ON j.id = s.journey_id "
                "WHERE s.id = %s AND s.uid = %s", (quiz_id, uid))
    return normalize(code) if code else user_language(uid)


def for_journey_or_user(journey_id: Optional[str], uid: Optional[str]) -> str:
    return journey_language(journey_id) if journey_id else user_language(uid)


def is_adult(uid: Optional[str]) -> bool:
    if not uid:
        return False
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT age_group_flag FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                return bool(row and row["age_group_flag"] == "adult")
    except Exception:
        return False


def allowed_language(uid: Optional[str], code: Optional[str]) -> str:
    """Non-English content is for adult accounts for now: the crisis check in chat
    and its response are English-only (see plans/feature-improvements F2.2)."""
    code = normalize(code)
    return code if code == DEFAULT_LANGUAGE or is_adult(uid) else DEFAULT_LANGUAGE
