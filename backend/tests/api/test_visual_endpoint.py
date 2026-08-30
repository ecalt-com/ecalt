"""API test for GET /journeys/{id}/steps/{id}/visual (plans/visual-intelligence).
Read-only endpoint — never triggers planning."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_UID


@pytest.fixture
def client():
    from app.main import app
    from app.core.auth import get_required_user, get_optional_user

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_required_user] = lambda: TEST_UID
    app.dependency_overrides[get_optional_user] = lambda: TEST_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


class TestGetStepVisual:
    def test_no_plan_yet_returns_pending(self, client):
        with patch("app.api.v1.endpoints.journeys.get_step_visual_row", return_value=None):
            r = client.get("/api/v1/journeys/j1/steps/s1/visual")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

    def test_planned_with_no_visual_returns_unavailable(self, client):
        row = {"selected_strategy": "TEXT_ONLY", "execution_status": "skipped", "vlo_id": None,
               "modality": None, "renderer_type": None, "recipe": None, "pedagogical_role": None}
        with patch("app.api.v1.endpoints.journeys.get_step_visual_row", return_value=row):
            r = client.get("/api/v1/journeys/j1/steps/s1/visual")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "unavailable"
        assert body["strategy"] == "TEXT_ONLY"

    def test_ready_returns_recipe(self, client):
        row = {
            "selected_strategy": "NATIVE_RENDER", "execution_status": "ready", "vlo_id": "vlo-1",
            "modality": "native_diagram", "renderer_type": "process_flow",
            "recipe": {"pattern": "process_flow", "title": "x", "nodes": [], "connections": []},
            "pedagogical_role": "explain",
            "asset_url": None, "asset_type": None, "asset_attribution": None, "asset_license_type": None,
        }
        with patch("app.api.v1.endpoints.journeys.get_step_visual_row", return_value=row):
            r = client.get("/api/v1/journeys/j1/steps/s1/visual")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["vlo_id"] == "vlo-1"
        assert body["renderer_type"] == "process_flow"
        assert body["recipe"]["pattern"] == "process_flow"
        assert body["asset_url"] is None

    def test_ready_returns_generated_image_asset(self, client):
        row = {
            "selected_strategy": "GENERATE_IMAGE", "execution_status": "ready", "vlo_id": "vlo-2",
            "modality": "generated_image", "renderer_type": None, "recipe": {},
            "pedagogical_role": "explain",
            "asset_url": "https://storage.example/visual-assets/abc.webp", "asset_type": "webp",
            "asset_attribution": None, "asset_license_type": "generated",
        }
        with patch("app.api.v1.endpoints.journeys.get_step_visual_row", return_value=row):
            r = client.get("/api/v1/journeys/j1/steps/s1/visual")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ready"
        assert body["renderer_type"] is None
        assert body["recipe"] is None
        assert body["asset_url"] == "https://storage.example/visual-assets/abc.webp"
        assert body["asset_type"] == "webp"
        assert body["license_type"] == "generated"

    def test_requires_auth(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/api/v1/journeys/j1/steps/s1/visual")
        assert r.status_code in (401, 403)
