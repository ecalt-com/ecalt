"""Visual Intelligence Layer (plans/visual-intelligence): recipe schema
validation for the first 10 native visual patterns."""
import pytest
from pydantic import ValidationError

from app.models.visual_schemas import VISUAL_PATTERNS
from app.models.visual_recipe_schemas import PATTERN_SCHEMAS, validate_recipe


class TestRegistryConsistency:
    def test_pattern_schemas_match_visual_patterns(self):
        assert set(PATTERN_SCHEMAS.keys()) == set(VISUAL_PATTERNS)


class TestProcessFlow:
    def test_valid_recipe(self):
        recipe = {
            "pattern": "process_flow",
            "title": "Photosynthesis",
            "nodes": [
                {"id": "sunlight", "label": "Sunlight", "role": "input"},
                {"id": "leaf", "label": "Leaf", "role": "process"},
                {"id": "glucose", "label": "Glucose", "role": "output"},
            ],
            "connections": [{"from": "sunlight", "to": "leaf"}, {"from": "leaf", "to": "glucose"}],
            "progressiveReveal": True,
        }
        validated = validate_recipe("process_flow", recipe)
        assert validated.nodes[0].role == "input"

    def test_too_few_nodes_rejected(self):
        recipe = {
            "pattern": "process_flow",
            "title": "x",
            "nodes": [{"id": "a", "label": "A", "role": "input"}],
            "connections": [],
        }
        with pytest.raises(ValidationError):
            validate_recipe("process_flow", recipe)

    def test_bad_role_rejected(self):
        recipe = {
            "pattern": "process_flow",
            "title": "x",
            "nodes": [
                {"id": "a", "label": "A", "role": "input"},
                {"id": "b", "label": "B", "role": "not-a-role"},
            ],
            "connections": [],
        }
        with pytest.raises(ValidationError):
            validate_recipe("process_flow", recipe)


class TestCycle:
    def test_valid_recipe(self):
        recipe = {
            "pattern": "cycle",
            "title": "Water Cycle",
            "nodes": [{"id": str(i), "label": f"Stage {i}"} for i in range(4)],
            "connections": [{"from": "0", "to": "1"}, {"from": "1", "to": "2"}, {"from": "2", "to": "0"}],
        }
        validate_recipe("cycle", recipe)

    def test_too_few_nodes_rejected(self):
        recipe = {"pattern": "cycle", "title": "x", "nodes": [{"id": "a", "label": "A"}], "connections": []}
        with pytest.raises(ValidationError):
            validate_recipe("cycle", recipe)


class TestHierarchy:
    def test_valid_shallow_tree(self):
        recipe = {
            "pattern": "hierarchy",
            "title": "Taxonomy",
            "nodes": [
                {"id": "kingdom", "label": "Animalia", "parentId": None},
                {"id": "phylum", "label": "Chordata", "parentId": "kingdom"},
            ],
        }
        validate_recipe("hierarchy", recipe)

    def test_excessive_depth_rejected(self):
        nodes = [{"id": "0", "label": "root", "parentId": None}]
        for i in range(1, 6):
            nodes.append({"id": str(i), "label": f"level {i}", "parentId": str(i - 1)})
        recipe = {"pattern": "hierarchy", "title": "Too Deep", "nodes": nodes}
        with pytest.raises(ValidationError):
            validate_recipe("hierarchy", recipe)


class TestQuantityComparison:
    def test_valid_recipe(self):
        recipe = {
            "pattern": "quantity_comparison",
            "title": "Planet Sizes",
            "items": [
                {"id": "earth", "label": "Earth", "value": 1, "unit": "Earth radii"},
                {"id": "jupiter", "label": "Jupiter", "value": 11.2, "unit": "Earth radii"},
            ],
        }
        validate_recipe("quantity_comparison", recipe)

    def test_negative_value_rejected(self):
        recipe = {
            "pattern": "quantity_comparison",
            "title": "x",
            "items": [
                {"id": "a", "label": "A", "value": -1},
                {"id": "b", "label": "B", "value": 2},
            ],
        }
        with pytest.raises(ValidationError):
            validate_recipe("quantity_comparison", recipe)


class TestComparison:
    def test_valid_two_column(self):
        recipe = {
            "pattern": "comparison",
            "title": "Mitosis vs Meiosis",
            "columns": [
                {"id": "mitosis", "label": "Mitosis", "items": ["2 daughter cells", "identical"]},
                {"id": "meiosis", "label": "Meiosis", "items": ["4 daughter cells", "genetically distinct"]},
            ],
        }
        validate_recipe("comparison", recipe)

    def test_single_column_rejected(self):
        recipe = {
            "pattern": "comparison",
            "title": "x",
            "columns": [{"id": "a", "label": "A", "items": ["x"]}],
        }
        with pytest.raises(ValidationError):
            validate_recipe("comparison", recipe)


class TestBeforeAfter:
    def test_valid_recipe(self):
        recipe = {
            "pattern": "before_after",
            "title": "Erosion",
            "before": {"label": "Before", "description": "Sharp cliff face"},
            "after": {"label": "After", "description": "Gently sloped hillside"},
        }
        validate_recipe("before_after", recipe)


class TestPartToWhole:
    def test_valid_recipe(self):
        recipe = {
            "pattern": "part_to_whole",
            "title": "The Cell",
            "whole": "Animal Cell",
            "parts": [
                {"id": "nucleus", "label": "Nucleus", "description": "Stores DNA"},
                {"id": "mito", "label": "Mitochondria", "description": "Produces energy"},
            ],
        }
        validate_recipe("part_to_whole", recipe)


class TestTimeline:
    def test_valid_recipe(self):
        recipe = {
            "pattern": "timeline",
            "title": "French Revolution",
            "events": [
                {"id": "1", "label": "Storming of the Bastille", "when": "1789"},
                {"id": "2", "label": "Execution of Louis XVI", "when": "1793"},
            ],
        }
        validate_recipe("timeline", recipe)


class TestProgressiveSequence:
    def test_valid_recipe(self):
        recipe = {
            "pattern": "progressive_sequence",
            "title": "Long Division",
            "steps": [
                {"id": "1", "label": "Divide", "content": "Divide the first digit"},
                {"id": "2", "label": "Multiply", "content": "Multiply and subtract"},
            ],
        }
        validate_recipe("progressive_sequence", recipe)


class TestUnknownPattern:
    def test_unknown_pattern_raises_key_error(self):
        with pytest.raises(KeyError):
            validate_recipe("not_a_real_pattern", {})
