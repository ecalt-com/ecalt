"""Visual Intelligence Layer (plans/visual-intelligence): cache-key hashing
determinism and VLO lookup query shape."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.services import visual_registry_service as reg


class TestHashing:
    def test_same_input_same_hash(self):
        assert reg.concept_hash("photosynthesis") == reg.concept_hash("photosynthesis")

    def test_case_and_whitespace_insensitive(self):
        assert reg.concept_hash("Photosynthesis") == reg.concept_hash("  photosynthesis  ")

    def test_different_input_different_hash(self):
        assert reg.concept_hash("photosynthesis") != reg.concept_hash("water-cycle")

    def test_objective_hash_is_independent_of_concept_hash(self):
        text = "understand the water cycle"
        assert reg.objective_hash(text) == reg.hash_text(text)


class TestFindReusableVlo:
    def test_none_modality_short_circuits_without_query(self):
        with patch("app.services.visual_registry_service.get_db") as mock_get_db:
            result = reg.find_reusable_vlo("photosynthesis", "obj", "all", "none")
        assert result is None
        mock_get_db.assert_not_called()

    def test_row_found_returns_dict(self):
        fake_cursor = MagicMock()
        fake_cursor.execute = MagicMock()
        fake_cursor.fetchone.return_value = {"id": "vlo-1", "status": "active"}

        fake_conn = MagicMock()
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

        @contextmanager
        def fake_get_db():
            yield fake_conn

        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            result = reg.find_reusable_vlo("photosynthesis", "understand light energy", "all", "native_diagram")

        assert result == {"id": "vlo-1", "status": "active"}
        args, _ = fake_cursor.execute.call_args
        query, params = args
        assert "status = 'active'" in query
        assert params[0] == "photosynthesis"
        assert params[2] == "all"
        assert params[3] == "native_diagram"

    def test_no_row_returns_none(self):
        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = None
        fake_conn = MagicMock()
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

        @contextmanager
        def fake_get_db():
            yield fake_conn

        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            result = reg.find_reusable_vlo("photosynthesis", "understand light energy", "all", "native_diagram")

        assert result is None


class TestGetStepVisual:
    def test_query_joins_assets(self):
        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = {
            "selected_strategy": "GENERATE_IMAGE", "vlo_id": "vlo-1", "asset_url": "https://x/y.webp",
        }
        fake_conn = MagicMock()
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

        @contextmanager
        def fake_get_db():
            yield fake_conn

        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            result = reg.get_step_visual("j1", "s1")

        assert result["asset_url"] == "https://x/y.webp"
        args, _ = fake_cursor.execute.call_args
        query, params = args
        assert "visual_assets" in query
        assert params == ("j1", "s1")

    def test_no_row_returns_none(self):
        fake_cursor = MagicMock()
        fake_cursor.fetchone.return_value = None
        fake_conn = MagicMock()
        fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

        @contextmanager
        def fake_get_db():
            yield fake_conn

        with patch("app.services.visual_registry_service.get_db", fake_get_db):
            result = reg.get_step_visual("j1", "s1")

        assert result is None
