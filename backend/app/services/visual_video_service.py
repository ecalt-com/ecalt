"""Visual Intelligence Layer — Phase 7: video generation gateway (interface only).

Spec section 30 is explicit that Phase 7 should NOT be implemented until the
data from Phases 2-6 shows real demand for it, measuring:
  - percentage of visual plans requiring true motion
  - percentage of those solvable by progressive/native animation instead
  - cost per successful learning outcome

Once VISUAL_TELEMETRY_ENABLED has been on long enough to answer those
questions (query visual_plans.plan->>'recommendedModality' = 'generated_video'
vs. how often NATIVE_RENDER/progressive_sequence already covers a "motion"
need), a concrete VideoGenerationProvider can be wired in here. Until then
this ships only the interface (spec section 18) so the router's
GENERATE_VIDEO branch has something typed to call — it always returns None,
so that branch can never actually execute, regardless of
VISUAL_VIDEO_GENERATION_ENABLED. No self-hosted GPU infrastructure, no video
model integration, in v1 (spec section 2 non-goals).
"""
from typing import Protocol


class VideoGenerationProvider(Protocol):
    name: str

    async def generate(self, prompt: str, duration_hint_s: float) -> dict:
        """Should return {"url"|"bytes", "content_type", "duration_ms"}."""
        ...


# Empty by design -- see module docstring.
VIDEO_PROVIDERS: dict[str, VideoGenerationProvider] = {}


async def generate_step_video(visual_description: str, uid: str | None) -> dict | None:
    """Always returns None in v1 -- no provider is registered. Never raises."""
    return None
