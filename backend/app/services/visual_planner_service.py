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
PLANNER_PROMPT_VERSION = 1

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

Do not recommend decorative visuals.

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
  "generationAllowed": false,
  "estimatedPedagogicalValue": 0.0
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
4. Does understanding require motion, spatial understanding, real-world context, interaction, or quantitative manipulation?
5. What is the lowest-cost effective modality?
6. If native rendering is possible, select a visual pattern from the fixed list.
7. Provide a concise visual description.
8. Provide fallbacks."""


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
        data = _loads_ai_json(raw)
        return VisualPlan(**data)
    except Exception:
        logger.exception("visual planner failed for step %r — falling back to text-only", step_title)
        return fallback
