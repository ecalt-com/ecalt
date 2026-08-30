"""Visual Intelligence Layer — Phase 1: the deterministic Visual Router.

The planner recommends; this decides. Pure function, no I/O, no LLM calls —
easy to unit test exhaustively (spec section 32). Mirrors the pseudocode in
spec section 9, with branches for capabilities this repo doesn't have yet
(native renderers land in Phase 2, retrieval in Phase 5, generation in
Phase 6) gated behind feature flags so they're inert until built.
"""
from dataclasses import dataclass

from app.models.visual_schemas import VISUAL_PATTERNS, VisualPlan, VisualStrategy


@dataclass
class RouterFlags:
    native_render_enabled: bool = False
    retrieval_enabled: bool = False
    image_generation_enabled: bool = False
    video_generation_enabled: bool = False


def select_strategy(
    plan: VisualPlan,
    existing_vlo: dict | None,
    flags: RouterFlags,
) -> VisualStrategy:
    if not plan.visualRequired:
        return "NONE"

    if existing_vlo is not None:
        return "REUSE_VLO"

    if flags.native_render_enabled and plan.visualPattern in VISUAL_PATTERNS:
        return "NATIVE_RENDER"

    if flags.retrieval_enabled and plan.conceptProperties.requiresRealWorldContext:
        return "RETRIEVE_LICENSED_ASSET"

    if flags.image_generation_enabled and plan.generationAllowed:
        return "GENERATE_IMAGE"

    if (
        flags.video_generation_enabled
        and plan.generationAllowed
        and plan.recommendedModality == "generated_video"
    ):
        return "GENERATE_VIDEO"

    return "TEXT_ONLY"
