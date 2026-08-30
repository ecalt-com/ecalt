"""Visual Intelligence Layer (plans/visual-intelligence Phase 3): version-aware
VLO reuse -- bumping RECIPE_PROMPT_VERSION should make old VLOs invisible to
reuse without deleting them."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.services import visual_registry_service as reg


def _fake_db(fetchone_return):
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = fetchone_return
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    @contextmanager
    def fake_get_db():
        yield fake_conn

    return fake_get_db, fake_cursor


class TestVersionAwareLookup:
    def test_min_version_passed_to_query(self):
        fake_get_db, fake_cursor = _fake_db({"id": "vlo-1", "version": 2})
        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            reg.find_reusable_vlo("photosynthesis", "obj", "all", "native_diagram", min_version=2)
        args, _ = fake_cursor.execute.call_args
        _, params = args
        assert params[-1] == 2

    def test_default_min_version_is_one(self):
        fake_get_db, fake_cursor = _fake_db(None)
        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            reg.find_reusable_vlo("photosynthesis", "obj", "all", "native_diagram")
        args, _ = fake_cursor.execute.call_args
        _, params = args
        assert params[-1] == 1


class TestCreateActiveVloVersion:
    def test_version_passed_through_to_insert(self):
        fake_get_db, fake_cursor = _fake_db({"id": "vlo-new"})
        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            vlo_id = reg.create_active_vlo(
                concept_key="photosynthesis", learning_objective="obj", grade_band="all",
                modality="native_diagram", pedagogical_role="explain", renderer_type="process_flow",
                recipe={"a": 1}, version=3,
            )
        assert vlo_id == "vlo-new"
        args, _ = fake_cursor.execute.call_args
        _, params = args
        assert params[-1] == 3

    def test_default_version_is_one(self):
        fake_get_db, fake_cursor = _fake_db({"id": "vlo-new"})
        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            reg.create_active_vlo(
                concept_key="photosynthesis", learning_objective="obj", grade_band="all",
                modality="native_diagram", pedagogical_role="explain", renderer_type="process_flow",
                recipe={"a": 1},
            )
        args, _ = fake_cursor.execute.call_args
        _, params = args
        assert params[-1] == 1


class TestEffectivenessScore:
    def test_set_effectiveness_score_updates_row(self):
        fake_get_db, fake_cursor = _fake_db(None)
        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            reg.set_effectiveness_score("vlo-1", 0.42)
        args, _ = fake_cursor.execute.call_args
        _, params = args
        assert params == (0.42, "vlo-1")
