"""API test for POST /admin/visual/test-image-generation (plans/visual-intelligence) —
diagnostic tool for isolating "pipeline broken" from "planner never needed it"."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_ADMIN_UID, TEST_UID


@pytest.fixture
def admin_client():
    from app.main import app
    from app.core.auth import get_admin_user

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_admin_user] = lambda: TEST_ADMIN_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture
def non_admin_client():
    from app.main import app
    from app.core.auth import get_admin_user
    from fastapi import HTTPException

    saved = dict(app.dependency_overrides)

    def _deny():
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[get_admin_user] = _deny

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


class TestAdminTestImageGeneration:
    def test_storage_not_configured_returns_503(self, admin_client):
        with patch("app.services.visual_image_service.images_enabled", return_value=False):
            r = admin_client.post("/api/v1/admin/visual/test-image-generation", json={"description": "a red apple"})
        assert r.status_code == 503

    def test_generation_failure_returns_502(self, admin_client):
        with (
            patch("app.services.visual_image_service.images_enabled", return_value=True),
            patch("app.services.visual_image_service.generate_step_visual", new=AsyncMock(return_value=None)),
        ):
            r = admin_client.post("/api/v1/admin/visual/test-image-generation", json={"description": "a red apple"})
        assert r.status_code == 502

    def test_happy_path_returns_url(self, admin_client):
        fake_result = {"url": "https://storage.example/visual-assets/x.webp", "model": "gpt-image-1-mini",
                       "content_type": "image/webp", "content_hash": "abc123", "size_bytes": 1000}
        with (
            patch("app.services.visual_image_service.images_enabled", return_value=True),
            patch("app.services.visual_image_service.generate_step_visual", new=AsyncMock(return_value=fake_result)) as mock_gen,
        ):
            r = admin_client.post("/api/v1/admin/visual/test-image-generation", json={"description": "a red apple"})
        assert r.status_code == 200
        assert r.json()["url"] == "https://storage.example/visual-assets/x.webp"
        # uid=None -- diagnostic runs are never charged to a user's budget.
        mock_gen.assert_called_once_with("a red apple", uid=None)

    def test_requires_admin(self, non_admin_client):
        r = non_admin_client.post("/api/v1/admin/visual/test-image-generation", json={"description": "a red apple"})
        assert r.status_code == 403
