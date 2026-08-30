"""Visual Intelligence Layer (plans/visual-intelligence): deterministic router
decision tree. Pure function — no mocking needed. Includes a few of the spec's
suggested golden fixtures (photosynthesis, water cycle) as router-only cases,
since there's no LLM call to make in a unit test."""
from app.models.visual_schemas import ConceptProperties, VisualConcept, VisualPlan
from app.services.visual_router_service import RouterFlags, select_strategy

ALL_OFF = RouterFlags()
ALL_ON = RouterFlags(
    native_render_enabled=True,
    retrieval_enabled=True,
    image_generation_enabled=True,
    video_generation_enabled=True,
)


def _plan(**overrides) -> VisualPlan:
    defaults = dict(
        visualRequired=True,
        concept=VisualConcept(canonicalName="Photosynthesis", conceptKey="photosynthesis"),
        learningObjective="Understand light energy conversion to chemical energy",
        pedagogicalRole="explain",
        conceptProperties=ConceptProperties(requiresMotion=True),
        recommendedModality="animated_process",
        visualPattern="process_flow",
        generationAllowed=False,
    )
    defaults.update(overrides)
    return VisualPlan(**defaults)


class TestSelectStrategy:
    def test_no_visual_required_returns_none(self):
        plan = _plan(visualRequired=False)
        assert select_strategy(plan, None, ALL_OFF) == "NONE"

    def test_existing_vlo_always_wins_reuse(self):
        plan = _plan()
        assert select_strategy(plan, {"id": "vlo-1"}, ALL_OFF) == "REUSE_VLO"
        # Even when every generation flag is on, reuse still takes priority.
        assert select_strategy(plan, {"id": "vlo-1"}, ALL_ON) == "REUSE_VLO"

    def test_all_flags_off_falls_back_to_text_only(self):
        plan = _plan()
        assert select_strategy(plan, None, ALL_OFF) == "TEXT_ONLY"

    def test_native_render_enabled_with_known_pattern(self):
        plan = _plan(visualPattern="process_flow")
        flags = RouterFlags(native_render_enabled=True)
        assert select_strategy(plan, None, flags) == "NATIVE_RENDER"

    def test_native_render_enabled_but_unknown_pattern_falls_through(self):
        plan = _plan(visualPattern="not_a_real_pattern")
        flags = RouterFlags(native_render_enabled=True)
        assert select_strategy(plan, None, flags) == "TEXT_ONLY"

    def test_native_render_enabled_but_no_pattern_falls_through(self):
        plan = _plan(visualPattern=None)
        flags = RouterFlags(native_render_enabled=True)
        assert select_strategy(plan, None, flags) == "TEXT_ONLY"

    def test_retrieval_requires_real_world_context(self):
        plan = _plan(
            visualPattern=None,
            conceptProperties=ConceptProperties(requiresRealWorldContext=True),
        )
        flags = RouterFlags(retrieval_enabled=True)
        assert select_strategy(plan, None, flags) == "RETRIEVE_LICENSED_ASSET"

    def test_retrieval_disabled_falls_through_despite_real_world_context(self):
        plan = _plan(
            visualPattern=None,
            conceptProperties=ConceptProperties(requiresRealWorldContext=True),
        )
        assert select_strategy(plan, None, ALL_OFF) == "TEXT_ONLY"

    def test_image_generation_requires_flag_and_allowed(self):
        plan = _plan(visualPattern=None, generationAllowed=True)
        flags = RouterFlags(image_generation_enabled=True)
        assert select_strategy(plan, None, flags) == "GENERATE_IMAGE"

    def test_image_generation_blocked_when_not_allowed_by_plan(self):
        plan = _plan(visualPattern=None, generationAllowed=False)
        flags = RouterFlags(image_generation_enabled=True)
        assert select_strategy(plan, None, flags) == "TEXT_ONLY"

    def test_video_requires_flag_allowed_and_recommended_modality(self):
        plan = _plan(
            visualPattern=None,
            generationAllowed=True,
            recommendedModality="generated_video",
        )
        flags = RouterFlags(video_generation_enabled=True)
        assert select_strategy(plan, None, flags) == "GENERATE_VIDEO"

    def test_video_flag_alone_is_not_enough(self):
        plan = _plan(
            visualPattern=None,
            generationAllowed=True,
            recommendedModality="animated_process",
        )
        flags = RouterFlags(video_generation_enabled=True)
        assert select_strategy(plan, None, flags) == "TEXT_ONLY"

    def test_priority_order_native_before_retrieval_before_generation(self):
        plan = _plan(
            visualPattern="process_flow",
            conceptProperties=ConceptProperties(requiresRealWorldContext=True),
            generationAllowed=True,
            recommendedModality="generated_video",
        )
        assert select_strategy(plan, None, ALL_ON) == "NATIVE_RENDER"


class TestGoldenFixtures:
    def test_photosynthesis_routes_to_process_flow_when_native_enabled(self):
        plan = _plan(
            concept=VisualConcept(canonicalName="Photosynthesis", conceptKey="photosynthesis"),
            visualPattern="process_flow",
        )
        flags = RouterFlags(native_render_enabled=True)
        assert select_strategy(plan, None, flags) == "NATIVE_RENDER"

    def test_water_cycle_routes_to_cycle_when_native_enabled(self):
        plan = _plan(
            concept=VisualConcept(canonicalName="Water Cycle", conceptKey="water-cycle"),
            visualPattern="cycle",
            conceptProperties=ConceptProperties(requiresMotion=True, requiresSpatialUnderstanding=True),
        )
        flags = RouterFlags(native_render_enabled=True)
        assert select_strategy(plan, None, flags) == "NATIVE_RENDER"

    def test_pythagorean_theorem_no_visual_needed(self):
        plan = _plan(
            visualRequired=False,
            concept=VisualConcept(canonicalName="Pythagorean Theorem", conceptKey="pythagorean-theorem"),
        )
        assert select_strategy(plan, None, ALL_ON) == "NONE"
