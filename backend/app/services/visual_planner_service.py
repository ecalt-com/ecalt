"""Visual Intelligence Layer — Phase 1: the Visual Planner.

The planner LLM decides *whether* a visual would materially help and *what
kind* — it never produces pixels, HTML, or executable output itself. The
deterministic VisualRouter (visual_router_service.py) turns its recommendation
into an actual execution strategy.

Standalone in Phase 1: nothing calls plan_visual() from the live journey/step
generation path yet (see backend/plans/visual-intelligence/README.md §2) —
there's no renderer to route to until Phase 2, so wiring this in now would
only spend tokens for no learner-visible benefit.
"""
import logging

from app.models.visual_schemas import VisualPlan, visual_plan_text_only
from app.services.ai_service import _loads_ai_json
from app.services.provider_service import complete_text

logger = logging.getLogger(__name__)

# Bump whenever the planner prompt/contract changes materially — mirrors
# ai_service.CONTENT_PROMPT_VERSION's role for step content.
# v2: generationAllowed was silently always false in prod -- the JSON
# schema's literal "generationAllowed": false example had no criteria
# attached anywhere, so the model just copied it verbatim every time. Added
# explicit decision criteria below instead of a biased example value.
# v3: estimatedPedagogicalValue came back as a 1-10 score (e.g. 8.0) instead
# of the required 0-1 fraction, failing VisualPlan's le=1 constraint and
# dropping the whole plan to text-only. Clarified the prompt AND added
# _normalize_plan_data() as a defensive backstop -- see its docstring.
# v4: content whose entire point is appearance ("what does the aurora look
# like") was getting recommendedModality=none, requiresRealWorldContext=false
# -- "do not recommend decorative visuals" was apparently read as "a photo
# is decorative unless it's a diagram-replaceable mechanism." Added an
# explicit appearance category so this kind of content routes toward
# retrieved_image instead of being skipped.
PLANNER_PROMPT_VERSION = 4

_SYSTEM_PROMPT = """\
You are ECALT Visual Intelligence Planner.

Your job is NOT to create an image, video, HTML, SVG, or animation.

Your job is to determine whether a visual learning experience would materially improve understanding of the supplied teaching content.

Prioritize learning effectiveness over visual attractiveness.

Use a visual only when it reduces cognitive effort or helps demonstrate:
- relationships
- motion
- process
- transformation
- structure
- comparison
- quantity
- spatial arrangement
- real-world context
- appearance (what a real thing actually looks like: its color, form, texture, or visual character)

Appearance is its own category, not a weaker version of "decorative" — when the learning objective genuinely IS what something looks like (the colors of an aurora, the texture of Roman concrete, the form of a coral reef, the visual style of a painting), no amount of text substitutes for seeing it, and a photo is exactly as functional as a diagram is for a process. Do not default to "none" for this kind of content just because it reads as descriptive prose rather than a mechanism — set requiresRealWorldContext: true and recommendedModality: "retrieved_image" (or "generated_image" only if the generationAllowed rule below applies) rather than skipping the visual.

Do not recommend visuals that are decorative in the sense of unrelated-to-the-content or purely ornamental (e.g. a generic stock photo next to a definition). A real photo whose subject IS the learning objective is never decorative.

Choose the lowest-cost modality capable of achieving the learning objective.

Preference order:
1. Reusable ECALT visual
2. Reusable native interactive visual
3. Reusable native diagram
4. Progressive reveal
5. Native animation
6. Existing educational simulation
7. Licensed/open real-world asset
8. Generated image
9. Generated video

Generated video is only appropriate when real motion, immersion, or visual reconstruction is essential and cannot be represented effectively using an interactive or animated diagram.

generationAllowed decision rule — set it to true ONLY when ALL of these hold:
- recommendedModality is "generated_image" or "generated_video" (i.e. every cheaper option in the preference order above genuinely fails the learning objective)
- No pattern in the fixed visualPattern list could reasonably represent this concept
- The concept is not better served by a real-world photo/video that licensed retrieval could supply instead (that's retrieved_image/retrieved_video, not generation)
In every other case — including when recommendedModality is anything else — generationAllowed must be false. Most steps should have generationAllowed: false; only recommend generation when you are confident nothing cheaper works.

Return ONLY a valid JSON object matching this exact structure — no markdown, no explanation:
{
  "version": "1.0",
  "visualRequired": true,
  "priority": "low | medium | high",
  "concept": {"canonicalName": "...", "conceptKey": "lowercase-hyphenated-key"},
  "learningObjective": "...",
  "pedagogicalRole": "hook | anchor | explain | compare | demonstrate | simulate | practice | recap",
  "conceptProperties": {
    "requiresMotion": true,
    "requiresSpatialUnderstanding": false,
    "requiresRealWorldContext": false,
    "benefitsFromInteraction": false,
    "requiresQuantitativeManipulation": false
  },
  "recommendedModality": "none | native_diagram | progressive_reveal | animated_process | interactive | simulation | retrieved_image | retrieved_video | generated_image | generated_video",
  "fallbackModalities": ["..."],
  "visualPattern": "process_flow | cycle | cause_effect | comparison | timeline | hierarchy | part_to_whole | before_after | quantity_comparison | progressive_sequence | null",
  "visualDescription": "concise description of what the visual should show",
  "generationAllowed": true or false, decided using the rule above — do not default this to false without applying the rule,
  "estimatedPedagogicalValue": a fraction between 0.0 and 1.0 (e.g. 0.75) — NOT a 1-10 score, never greater than 1.0
}"""

_USER_PROMPT_TEMPLATE = """\
CURRENT LESSON:
{step_title}

LEARNER:
Age group: {age_group}
Level: {difficulty}

CURRENT CONTENT BLOCK:
{content}

LEARNING OBJECTIVE:
{learning_objective}

Determine:
1. Is a visual materially useful?
2. What is its pedagogical role?
3. What concept must the learner understand?
4. Does understanding require motion, spatial understanding, real-world context, interaction, or quantitative manipulation? Is the learning objective itself about what something looks like (appearance/color/visual character) — if so, treat that as real-world context requiring a visual, not as prose that needs no visual.
5. What is the lowest-cost effective modality?
6. If native rendering is possible, select a visual pattern from the fixed list.
7. Provide a concise visual description.
8. Provide fallbacks.
9. Only if no native pattern or retrieval could work: is generation actually justified? Apply the generationAllowed rule."""


def _normalize_plan_data(data: dict) -> dict:
    """Repairs the one field models reliably get wrong despite explicit
    instructions: estimatedPedagogicalValue coming back as a 1-10 score
    instead of a 0-1 fraction (spotted in prod: 8.0, which failed
    VisualPlan's le=1 constraint and took the whole plan down with it).
    Rescale/clamp defensively rather than let one stray number fail
    validation for an otherwise-good plan."""
    value = data.get("estimatedPedagogicalValue")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > 1:
            value = value / 10 if value <= 10 else 1.0
        data["estimatedPedagogicalValue"] = max(0.0, min(1.0, float(value)))
    return data


def build_user_prompt(step_title: str, content: str, learning_objective: str, age_group: str, difficulty: str) -> str:
    return _USER_PROMPT_TEMPLATE.format(
        step_title=step_title,
        age_group=age_group,
        difficulty=difficulty,
        content=content[:4000],
        learning_objective=learning_objective,
    )


async def plan_visual(
    step_title: str,
    content: str,
    learning_objective: str,
    age_group: str = "all",
    difficulty: str = "beginner",
) -> VisualPlan:
    """Ask the planner LLM whether/how a visual should represent this step.

    Never raises — any failure (provider error, invalid JSON, schema
    validation failure) degrades to a text-only plan so a planner outage can
    never block journey/step generation (spec section 27).
    """
    concept_key = step_title.strip().lower() or "concept"
    fallback = visual_plan_text_only(concept_key, learning_objective)

    try:
        user_prompt = build_user_prompt(step_title, content, learning_objective, age_group, difficulty)
        raw, _, _, _ = await complete_text("visual_planner", _SYSTEM_PROMPT, user_prompt, max_tokens=600)
        data = _normalize_plan_data(_loads_ai_json(raw))
        return VisualPlan(**data)
    except Exception:
        logger.exception("visual planner failed for step %r — falling back to text-only", step_title)
        return fallback
