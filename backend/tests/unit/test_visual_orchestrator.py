"""Visual Intelligence Layer (plans/visual-intelligence): orchestrator
integration of planner -> registry -> router -> recipe generation ->
persistence, with everything except settings mocked out."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.models.visual_schemas import ConceptProperties, VisualConcept, VisualPlan, visual_plan_text_only
from app.services import visual_orchestrator_service as orch


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


class TestFeatureFlagGate:
    @pytest.mark.asyncio
    async def test_disabled_short_circuits_with_no_ai_calls(self, monkeypatch):
        monkeypatch.setattr(settings, "VISUAL_INTELLIGENCE_ENABLED", False)
        with patch("app.services.visual_orchestrator_service.visual_planner_service.plan_visual", new=AsyncMock()) as mock_plan:
            result = await orch.plan_visual_for_step(
                journey_id="j1", step_id="s1", step_title="Photosynthesis",
                content="...", learning_objective="...",
            )
        assert result == {"status": "skipped", "strategy": "NONE", "plan_id": None, "vlo_id": None}
        mock_plan.assert_not_called()


class TestEnabledOrchestration:
    @pytest.mark.asyncio
    async def test_no_visual_required_persists_none_strategy(self, monkeypatch):
        monkeypatch.setattr(settings, "VISUAL_INTELLIGENCE_ENABLED", True)
        no_visual_plan = visual_plan_text_only("photosynthesis", "obj")
        with (
            patch("app.services.visual_orchestrator_service.visual_planner_service.plan_visual", new=AsyncMock(return_value=no_visual_plan)),
            patch("app.services.visual_orchestrator_service.visual_registry_service.upsert_visual_plan", return_value="plan-1") as mock_upsert,
        ):
            result = await orch.plan_visual_for_step(
                journey_id="j1", step_id="s1", step_title="Photosynthesis",
                content="...", learning_objective="obj",
            )
        assert result["strategy"] == "NONE"
        assert result["vlo_id"] is None
        assert mock_upsert.call_args.kwargs["execution_status"] == "skipped"

    @pytest.mark.asyncio
    async def test_existing_vlo_reused_without_recipe_generation(self, monkeypatch):
        monkeypatch.setattr(settings, "VISUAL_INTELLIGENCE_ENABLED", True)
        plan = _plan()
        with (
            patch("app.services.visual_orchestrator_service.visual_planner_service.plan_visual", new=AsyncMock(return_value=plan)),
            patch("app.services.visual_orchestrator_service.visual_registry_service.find_reusable_vlo", return_value={"id": "vlo-existing"}),
            patch("app.services.visual_orchestrator_service.visual_registry_service.record_vlo_reuse") as mock_reuse,
            patch("app.services.visual_orchestrator_service.visual_registry_service.upsert_visual_plan", return_value="plan-1"),
            patch("app.services.visual_orchestrator_service.visual_recipe_service.generate_recipe", new=AsyncMock()) as mock_recipe,
        ):
            result = await orch.plan_visual_for_step(
                journey_id="j1", step_id="s1", step_title="Photosynthesis",
                content="...", learning_objective=plan.learningObjective,
            )
        assert result["strategy"] == "REUSE_VLO"
        assert result["vlo_id"] == "vlo-existing"
        mock_reuse.assert_called_once_with("vlo-existing")
        mock_recipe.assert_not_called()

    @pytest.mark.asyncio
    async def test_native_render_success_creates_vlo(self, monkeypatch):
        monkeypatch.setattr(settings, "VISUAL_INTELLIGENCE_ENABLED", True)
        monkeypatch.setattr(settings, "VISUAL_NATIVE_RENDER_ENABLED", True)
        plan = _plan()
        recipe = {"pattern": "process_flow", "title": "x", "nodes": [], "connections": []}
        with (
            patch("app.services.visual_orchestrator_service.visual_planner_service.plan_visual", new=AsyncMock(return_value=plan)),
            patch("app.services.visual_orchestrator_service.visual_registry_service.find_reusable_vlo", return_value=None),
            patch("app.services.visual_orchestrator_service.visual_recipe_service.generate_recipe", new=AsyncMock(return_value=recipe)),
            patch("app.services.visual_orchestrator_service.visual_registry_service.create_active_vlo", return_value="vlo-new") as mock_create,
            patch("app.services.visual_orchestrator_service.visual_registry_service.upsert_visual_plan", return_value="plan-1") as mock_upsert,
        ):
            result = await orch.plan_visual_for_step(
                journey_id="j1", step_id="s1", step_title="Photosynthesis",
                content="...", learning_objective=plan.learningObjective,
            )
        assert result["strategy"] == "NATIVE_RENDER"
        assert result["vlo_id"] == "vlo-new"
        mock_create.assert_called_once()
        assert mock_upsert.call_args.kwargs["execution_status"] == "ready"

    @pytest.mark.asyncio
    async def test_native_render_recipe_failure_downgrades_to_text_only(self, monkeypatch):
        monkeypatch.setattr(settings, "VISUAL_INTELLIGENCE_ENABLED", True)
        monkeypatch.setattr(settings, "VISUAL_NATIVE_RENDER_ENABLED", True)
        plan = _plan()
        with (
            patch("app.services.visual_orchestrator_service.visual_planner_service.plan_visual", new=AsyncMock(return_value=plan)),
            patch("app.services.visual_orchestrator_service.visual_registry_service.find_reusable_vlo", return_value=None),
            patch("app.services.visual_orchestrator_service.visual_recipe_service.generate_recipe", new=AsyncMock(return_value=None)),
            patch("app.services.visual_orchestrator_service.visual_registry_service.create_active_vlo") as mock_create,
            patch("app.services.visual_orchestrator_service.visual_registry_service.upsert_visual_plan", return_value="plan-1") as mock_upsert,
        ):
            result = await orch.plan_visual_for_step(
                journey_id="j1", step_id="s1", step_title="Photosynthesis",
                content="...", learning_objective=plan.learningObjective,
            )
        assert result["strategy"] == "TEXT_ONLY"
        assert result["vlo_id"] is None
        mock_create.assert_not_called()
        assert mock_upsert.call_args.kwargs["execution_status"] == "skipped"

    @pytest.mark.asyncio
    async def test_retrieval_only_runs_for_adults_grade_band(self, monkeypatch):
        monkeypatch.setattr(settings, "VISUAL_INTELLIGENCE_ENABLED", True)
        monkeypatch.setattr(settings, "VISUAL_RETRIEVAL_ENABLED", True)
        plan = _plan(
            visualPattern=None,
            conceptProperties=ConceptProperties(requiresRealWorldContext=True),
        )
        with (
            patch("app.services.visual_orchestrator_service.visual_planner_service.plan_visual", new=AsyncMock(return_value=plan)),
            patch("app.services.visual_orchestrator_service.visual_registry_service.find_reusable_vlo", return_value=None),
            patch("app.services.visual_orchestrator_service.visual_retrieval_service.retrieve_licensed_asset", new=AsyncMock()) as mock_retrieve,
            patch("app.services.visual_orchestrator_service.visual_registry_service.upsert_visual_plan", return_value="plan-1"),
        ):
            result = await orch.plan_visual_for_step(
                journey_id="j1", step_id="s1", step_title="x", content="x",
                learning_objective=plan.learningObjective, age_group="kids",
            )
        assert result["strategy"] == "TEXT_ONLY"
        mock_retrieve.assert_not_called()

    @pytest.mark.asyncio
    async def test_planner_exception_never_propagates(self, monkeypatch):
        monkeypatch.setattr(settings, "VISUAL_INTELLIGENCE_ENABLED", True)
        with patch(
            "app.services.visual_orchestrator_service.visual_planner_service.plan_visual",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await orch.plan_visual_for_step(
                journey_id="j1", step_id="s1", step_title="x", content="x", learning_objective="x",
            )
        assert result == {"status": "skipped", "strategy": "NONE", "plan_id": None, "vlo_id": None}
