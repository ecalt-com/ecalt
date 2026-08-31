"""Visual Intelligence Layer (plans/visual-intelligence): recipe generation
graceful degradation."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services import visual_recipe_service

VALID_PROCESS_FLOW_JSON = """{
  "pattern": "process_flow",
  "title": "Photosynthesis",
  "nodes": [
    {"id": "sunlight", "label": "Sunlight", "role": "input"},
    {"id": "leaf", "label": "Leaf", "role": "process"},
    {"id": "glucose", "label": "Glucose", "role": "output"}
  ],
  "connections": [{"from": "sunlight", "to": "leaf"}, {"from": "leaf", "to": "glucose"}],
  "progressiveReveal": true
}"""


class TestGenerateRecipe:
    @pytest.mark.asyncio
    async def test_happy_path_returns_validated_dict(self):
        with patch(
            "app.services.visual_recipe_service.complete_text",
            new=AsyncMock(return_value=(VALID_PROCESS_FLOW_JSON, 50, 80, 0)),
        ):
            recipe = await visual_recipe_service.generate_recipe(
                pattern="process_flow",
                step_title="Photosynthesis",
                content="Plants convert sunlight into chemical energy in the leaf.",
                visual_description="Sunlight entering a leaf and becoming glucose",
            )
        assert recipe is not None
        assert recipe["pattern"] == "process_flow"
        assert recipe["nodes"][0]["role"] == "input"

    @pytest.mark.asyncio
    async def test_unknown_pattern_returns_none_without_calling_provider(self):
        with patch("app.services.visual_recipe_service.complete_text", new=AsyncMock()) as mock_complete:
            recipe = await visual_recipe_service.generate_recipe(
                pattern="not_a_real_pattern",
                step_title="x",
                content="x",
                visual_description="x",
            )
        assert recipe is None
        mock_complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_json_returns_none(self):
        with patch(
            "app.services.visual_recipe_service.complete_text",
            new=AsyncMock(return_value=("not json", 10, 5, 0)),
        ):
            recipe = await visual_recipe_service.generate_recipe(
                pattern="process_flow",
                step_title="x",
                content="x",
                visual_description="x",
            )
        assert recipe is None

    @pytest.mark.asyncio
    async def test_schema_violation_returns_none(self):
        bad_json = '{"pattern": "process_flow", "title": "x", "nodes": [], "connections": []}'
        with patch(
            "app.services.visual_recipe_service.complete_text",
            new=AsyncMock(return_value=(bad_json, 10, 5, 0)),
        ):
            recipe = await visual_recipe_service.generate_recipe(
                pattern="process_flow",
                step_title="x",
                content="x",
                visual_description="x",
            )
        assert recipe is None

    @pytest.mark.asyncio
    async def test_provider_error_returns_none(self):
        with patch(
            "app.services.visual_recipe_service.complete_text",
            new=AsyncMock(side_effect=RuntimeError("provider down")),
        ):
            recipe = await visual_recipe_service.generate_recipe(
                pattern="process_flow",
                step_title="x",
                content="x",
                visual_description="x",
            )
        assert recipe is None

    @pytest.mark.asyncio
    async def test_first_attempt_malformed_second_attempt_succeeds(self):
        mock_complete = AsyncMock(side_effect=[
            ("not json", 10, 5, 0),
            (VALID_PROCESS_FLOW_JSON, 50, 80, 0),
        ])
        with patch("app.services.visual_recipe_service.complete_text", new=mock_complete):
            recipe = await visual_recipe_service.generate_recipe(
                pattern="process_flow",
                step_title="Photosynthesis",
                content="x",
                visual_description="x",
            )
        assert recipe is not None
        assert recipe["pattern"] == "process_flow"
        assert mock_complete.call_count == 2

    @pytest.mark.asyncio
    async def test_both_attempts_fail_calls_provider_exactly_twice(self):
        mock_complete = AsyncMock(return_value=("not json", 10, 5, 0))
        with patch("app.services.visual_recipe_service.complete_text", new=mock_complete):
            recipe = await visual_recipe_service.generate_recipe(
                pattern="process_flow",
                step_title="x",
                content="x",
                visual_description="x",
            )
        assert recipe is None
        assert mock_complete.call_count == 2
