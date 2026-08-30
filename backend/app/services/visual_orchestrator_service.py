"""Visual Intelligence Layer — the Visual Orchestrator.

Entry point that ties planner -> registry lookup -> router -> execution ->
persistence together for a single journey step. Called from
ai_service.warm_journey_steps() after step content is already cached, inside
the same BackgroundTasks context image generation uses, so a slow/failed
visual plan never delays or breaks the learner-visible content. Everything
here is inert while settings.VISUAL_INTELLIGENCE_ENABLED is False (the
default — see backend/plans/visual-intelligence/README.md section 2).

Execution order mirrors spec section 16: the router picks the best strategy
given the plan + feature flags, but if executing it fails (recipe generation
error, no retrieval candidate, generation budget exhausted, ...), we fall
through to the next cheaper strategy rather than giving up outright (spec
section 27: "Retrieval failure -> try next strategy"). Each _try_* helper
re-checks its own flag/plan condition, so walking the whole remaining chain
is safe even when some of it is disabled.
"""
import logging

from app.core.config import settings
from app.models.visual_schemas import VisualPlan
from app.services import (
    visual_image_service,
    visual_planner_service,
    visual_recipe_service,
    visual_registry_service,
    visual_retrieval_service,
    visual_video_service,
)
from app.services.provider_service import get_config
from app.services.visual_router_service import RouterFlags, select_strategy

logger = logging.getLogger(__name__)

_STRATEGY_ORDER = ["NATIVE_RENDER", "RETRIEVE_LICENSED_ASSET", "GENERATE_IMAGE", "GENERATE_VIDEO"]


async def _try_native_render(plan: VisualPlan, step_title: str, content: str, grade_band: str, learning_objective: str) -> str | None:
    if not (settings.VISUAL_NATIVE_RENDER_ENABLED and plan.visualPattern):
        return None
    recipe = await visual_recipe_service.generate_recipe(
        pattern=plan.visualPattern, step_title=step_title, content=content,
        visual_description=plan.visualDescription,
    )
    if recipe is None:
        return None
    return visual_registry_service.create_active_vlo(
        concept_key=plan.concept.conceptKey, learning_objective=learning_objective, grade_band=grade_band,
        modality=plan.recommendedModality, pedagogical_role=plan.pedagogicalRole,
        renderer_type=plan.visualPattern, recipe=recipe, version=visual_recipe_service.RECIPE_PROMPT_VERSION,
    )


async def _try_retrieval(plan: VisualPlan, grade_band: str, learning_objective: str) -> str | None:
    if not (settings.VISUAL_RETRIEVAL_ENABLED and plan.conceptProperties.requiresRealWorldContext):
        return None
    query = plan.visualDescription or plan.concept.canonicalName
    candidate = await visual_retrieval_service.retrieve_licensed_asset(query, grade_band)
    if candidate is None:
        return None
    vlo_id = visual_registry_service.create_active_vlo(
        concept_key=plan.concept.conceptKey, learning_objective=learning_objective, grade_band=grade_band,
        modality="retrieved_image", pedagogical_role=plan.pedagogicalRole, renderer_type=None, recipe={},
    )
    visual_registry_service.create_visual_asset(
        vlo_id, asset_type="external_embed", external_url=candidate.external_url,
        source_type=candidate.license.source, source_name=candidate.license.source,
        license_type=candidate.license.license, license_url=candidate.license.license_url,
        attribution=candidate.license.attribution,
        commercial_use_allowed=candidate.license.commercial_use_allowed,
        modification_allowed=candidate.license.modification_allowed,
        width=candidate.width, height=candidate.height,
    )
    return vlo_id


async def _try_image_generation(plan: VisualPlan, grade_band: str, learning_objective: str, uid: str | None) -> str | None:
    if not (settings.VISUAL_IMAGE_GENERATION_ENABLED and plan.generationAllowed):
        return None
    result = await visual_image_service.generate_step_visual(plan.visualDescription or plan.concept.canonicalName, uid)
    if result is None:
        return None
    vlo_id = visual_registry_service.create_active_vlo(
        concept_key=plan.concept.conceptKey, learning_objective=learning_objective, grade_band=grade_band,
        modality="generated_image", pedagogical_role=plan.pedagogicalRole, renderer_type=None, recipe={},
    )
    visual_registry_service.create_visual_asset(
        vlo_id, asset_type="webp", external_url=result["url"],
        source_type="ai_generated", source_name=result["model"],
        license_type="generated", commercial_use_allowed=True, modification_allowed=True,
        file_size_bytes=result["size_bytes"],
    )
    return vlo_id


async def _try_video_generation(plan: VisualPlan, uid: str | None) -> str | None:
    if not (settings.VISUAL_VIDEO_GENERATION_ENABLED and plan.generationAllowed
            and plan.recommendedModality == "generated_video"):
        return None
    # Always None -- see visual_video_service module docstring (Phase 7
    # deliberately not implemented until demand is measured).
    return await visual_video_service.generate_step_video(plan.visualDescription, uid)


async def plan_visual_for_step(
    journey_id: str,
    step_id: str,
    step_title: str,
    content: str,
    learning_objective: str,
    age_group: str = "all",
    difficulty: str = "beginner",
    uid: str | None = None,
) -> dict:
    """Plan, route, and (when enabled) execute the visual for one journey step.

    Returns a dict of {status, strategy, plan_id, vlo_id} rather than raising
    — a visual failure must never make the lesson unreadable (spec section
    27). status is "skipped" when the feature is disabled or planning itself
    failed outright (belt-and-suspenders on top of the planner's own
    text-only fallback).
    """
    if not settings.VISUAL_INTELLIGENCE_ENABLED:
        return {"status": "skipped", "strategy": "NONE", "plan_id": None, "vlo_id": None}

    try:
        plan = await visual_planner_service.plan_visual(
            step_title=step_title,
            content=content,
            learning_objective=learning_objective,
            age_group=age_group,
            difficulty=difficulty,
        )

        grade_band = age_group
        existing_vlo = None
        if plan.visualRequired:
            existing_vlo = visual_registry_service.find_reusable_vlo(
                concept_key=plan.concept.conceptKey,
                learning_objective=learning_objective,
                grade_band=grade_band,
                modality=plan.recommendedModality,
                min_version=visual_recipe_service.RECIPE_PROMPT_VERSION,
            )

        flags = RouterFlags(
            native_render_enabled=settings.VISUAL_NATIVE_RENDER_ENABLED,
            retrieval_enabled=settings.VISUAL_RETRIEVAL_ENABLED,
            image_generation_enabled=settings.VISUAL_IMAGE_GENERATION_ENABLED,
            video_generation_enabled=settings.VISUAL_VIDEO_GENERATION_ENABLED,
        )
        strategy = select_strategy(plan, existing_vlo, flags)

        if existing_vlo is not None:
            visual_registry_service.record_vlo_reuse(existing_vlo["id"])
        elif strategy in _STRATEGY_ORDER:
            for candidate in _STRATEGY_ORDER[_STRATEGY_ORDER.index(strategy):]:
                if candidate == "NATIVE_RENDER":
                    vlo_id = await _try_native_render(plan, step_title, content, grade_band, learning_objective)
                elif candidate == "RETRIEVE_LICENSED_ASSET":
                    vlo_id = await _try_retrieval(plan, grade_band, learning_objective)
                elif candidate == "GENERATE_IMAGE":
                    vlo_id = await _try_image_generation(plan, grade_band, learning_objective, uid)
                else:  # GENERATE_VIDEO
                    vlo_id = await _try_video_generation(plan, uid)
                if vlo_id:
                    strategy = candidate
                    existing_vlo = {"id": vlo_id}
                    break
            else:
                strategy = "TEXT_ONLY"

        execution_status = "ready" if existing_vlo else ("skipped" if strategy in ("NONE", "TEXT_ONLY") else "planned")

        plan_id = visual_registry_service.upsert_visual_plan(
            journey_id=journey_id,
            step_id=step_id,
            concept_key=plan.concept.conceptKey,
            plan=plan,
            planner_model=get_config("visual_planner")["model"],
            selected_strategy=strategy,
            execution_status=execution_status,
            vlo_id=existing_vlo["id"] if existing_vlo else None,
            planner_prompt_version=visual_planner_service.PLANNER_PROMPT_VERSION,
        )

        return {
            "status": "planned",
            "strategy": strategy,
            "plan_id": plan_id,
            "vlo_id": existing_vlo["id"] if existing_vlo else None,
        }
    except Exception:
        logger.exception("visual orchestration failed for step %s/%s", journey_id, step_id)
        return {"status": "skipped", "strategy": "NONE", "plan_id": None, "vlo_id": None}
