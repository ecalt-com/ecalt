"""Visual Intelligence Layer — Phase 2: recipe generation for native renderers.

Turns a VisualPlan's chosen pattern plus the step's own lesson content into a
structured, schema-validated recipe (spec section 11) a future renderer can
draw deterministically. Still "generate instructions, not pixels" (spec
section 1) — the LLM only ever produces typed JSON, never markup or
executable code, and nothing becomes a VLO until it validates against its
pattern's schema (visual_recipe_schemas.validate_recipe).
"""
import logging

from app.models.visual_recipe_schemas import validate_recipe
from app.services.ai_service import _loads_ai_json
from app.services.provider_service import complete_text

logger = logging.getLogger(__name__)

RECIPE_PROMPT_VERSION = 1

_SYSTEM_PROMPT_TEMPLATE = """\
You are ECALT's Visual Recipe Generator. You do not draw anything or write \
HTML/SVG/JavaScript -- you extract the structured data a deterministic \
renderer needs to draw a "{pattern}" diagram from the lesson content below.

Rules:
- Every id/label must be grounded in a real term from the supplied content \
-- never invent facts, numbers, or relationships that are not present in it.
- Keep labels short (under 8 words) and free of markdown formatting.
- Return ONLY a valid JSON object matching this exact structure -- no \
markdown, no explanation, no extra keys:
{schema_hint}"""

_SCHEMA_HINTS: dict[str, str] = {
    "process_flow": '{"pattern":"process_flow","title":"...","nodes":[{"id":"...","label":"...","role":"input|process|output"}],"connections":[{"from":"...","to":"..."}],"progressiveReveal":true}',
    "cycle": '{"pattern":"cycle","title":"...","nodes":[{"id":"...","label":"..."}],"connections":[{"from":"...","to":"..."}],"progressiveReveal":true,"looping":true}',
    "cause_effect": '{"pattern":"cause_effect","title":"...","nodes":[{"id":"...","label":"...","role":"cause|mechanism|effect"}],"connections":[{"from":"...","to":"..."}]}',
    "comparison": '{"pattern":"comparison","title":"...","columns":[{"id":"...","label":"...","items":["..."]}]}',
    "timeline": '{"pattern":"timeline","title":"...","events":[{"id":"...","label":"...","when":"..."}],"progressiveReveal":true}',
    "hierarchy": '{"pattern":"hierarchy","title":"...","nodes":[{"id":"...","label":"...","parentId":"... or null"}]}',
    "part_to_whole": '{"pattern":"part_to_whole","title":"...","whole":"...","parts":[{"id":"...","label":"...","description":"..."}]}',
    "before_after": '{"pattern":"before_after","title":"...","before":{"label":"...","description":"..."},"after":{"label":"...","description":"..."}}',
    "quantity_comparison": '{"pattern":"quantity_comparison","title":"...","items":[{"id":"...","label":"...","value":0,"unit":"..."}]}',
    "progressive_sequence": '{"pattern":"progressive_sequence","title":"...","steps":[{"id":"...","label":"...","content":"..."}],"autoPlay":false}',
}


async def generate_recipe(pattern: str, step_title: str, content: str, visual_description: str) -> dict | None:
    """Returns a schema-validated recipe dict (aliases applied, e.g.
    "from"/"to"), or None if generation/validation fails. Callers must treat
    None as "fall back to a cheaper strategy", never as a hard error (spec
    section 27: renderer failure -> text remains usable)."""
    schema_hint = _SCHEMA_HINTS.get(pattern)
    if schema_hint is None:
        return None

    system = _SYSTEM_PROMPT_TEMPLATE.format(pattern=pattern, schema_hint=schema_hint)
    user = (
        f"LESSON: {step_title}\n\n"
        f"WHAT THE VISUAL SHOULD SHOW: {visual_description}\n\n"
        f"CONTENT:\n{content[:4000]}"
    )

    # One retry: LLM structured-output misses (a wrong-case enum value, an
    # extra key, a truncated response) are common enough on a first attempt
    # that giving up immediately downgrades a NATIVE_RENDER-worthy step to
    # TEXT_ONLY more often than necessary -- same "try twice" pattern
    # ai_service.warm_journey_steps() already uses for step content.
    for attempt in (1, 2):
        try:
            raw, _, _, _ = await complete_text("visual_recipe", system, user, max_tokens=700)
            data = _loads_ai_json(raw)
            validated = validate_recipe(pattern, data)
            return validated.model_dump(by_alias=True)
        except Exception:
            logger.warning(
                "visual recipe generation failed for pattern=%s step=%r attempt=%d",
                pattern, step_title, attempt, exc_info=True,
            )
    return None
