"""Visual Intelligence Layer (plans/visual-intelligence): planner schema validation
and graceful degradation on provider/parse failure."""
from unittest.mock import AsyncMock, patch

import pytest

from app.models.visual_schemas import VisualPlan, visual_plan_text_only
from app.services import visual_planner_service


VALID_PLAN_JSON = """{
  "version": "1.0",
  "visualRequired": true,
  "priority": "high",
  "concept": {"canonicalName": "Photosynthesis", "conceptKey": "photosynthesis"},
  "learningObjective": "Understand light energy conversion to chemical energy",
  "pedagogicalRole": "explain",
  "conceptProperties": {
    "requiresMotion": true,
    "requiresSpatialUnderstanding": false,
    "requiresRealWorldContext": false,
    "benefitsFromInteraction": false,
    "requiresQuantitativeManipulation": false
  },
  "recommendedModality": "animated_process",
  "fallbackModalities": ["native_diagram"],
  "visualPattern": "process_flow",
  "visualDescription": "Sunlight entering a leaf and becoming glucose",
  "generationAllowed": false,
  "estimatedPedagogicalValue": 0.8
}"""


class TestVisualPlanSchema:
    def test_valid_plan_parses(self):
        import json
        plan = VisualPlan(**json.loads(VALID_PLAN_JSON))
        assert plan.visualRequired is True
        assert plan.visualPattern == "process_flow"

    def test_text_only_fallback_never_requires_visual(self):
        plan = visual_plan_text_only("dna", "Understand DNA structure")
        assert plan.visualRequired is False
        assert plan.recommendedModality == "none"


class TestPlanVisual:
    @pytest.mark.asyncio
    async def test_happy_path_returns_validated_plan(self):
        with patch(
            "app.services.visual_planner_service.complete_text",
            new=AsyncMock(return_value=(VALID_PLAN_JSON, 100, 50, 0)),
        ):
            plan = await visual_planner_service.plan_visual(
                step_title="Photosynthesis",
                content="Plants convert sunlight into chemical energy...",
                learning_objective="Understand light energy conversion to chemical energy",
            )
        assert plan.visualRequired is True
        assert plan.concept.conceptKey == "photosynthesis"

    @pytest.mark.asyncio
    async def test_malformed_json_falls_back_to_text_only(self):
        with patch(
            "app.services.visual_planner_service.complete_text",
            new=AsyncMock(return_value=("not json at all", 10, 5, 0)),
        ):
            plan = await visual_planner_service.plan_visual(
                step_title="Photosynthesis",
                content="...",
                learning_objective="Understand light energy conversion",
            )
        assert plan.visualRequired is False

    @pytest.mark.asyncio
    async def test_provider_error_falls_back_to_text_only(self):
        with patch(
            "app.services.visual_planner_service.complete_text",
            new=AsyncMock(side_effect=RuntimeError("provider down")),
        ):
            plan = await visual_planner_service.plan_visual(
                step_title="Photosynthesis",
                content="...",
                learning_objective="Understand light energy conversion",
            )
        assert plan.visualRequired is False

    @pytest.mark.asyncio
    async def test_schema_violation_falls_back_to_text_only(self):
        bad_json = '{"version": "1.0", "visualRequired": "not-a-bool"}'
        with patch(
            "app.services.visual_planner_service.complete_text",
            new=AsyncMock(return_value=(bad_json, 10, 5, 0)),
        ):
            plan = await visual_planner_service.plan_visual(
                step_title="Photosynthesis",
                content="...",
                learning_objective="Understand light energy conversion",
            )
        assert plan.visualRequired is False
