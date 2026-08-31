"""API test for POST /journeys/{id}/steps/{id}/visual/events (plans/visual-intelligence)."""
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


class TestPostVisualEvent:
    def test_disabled_returns_disabled_status_without_touching_db(self, client, monkeypatch):
        # Explicit, not ambient: this asserts the *behavior* when the flag is
        # off, not "whatever the local/deployed env's default happens to be"
        # -- VISUAL_TELEMETRY_ENABLED may be true in some environments (it's
        # a runtime setting, not a constant), and asserting on that ambient
        # state previously let this test slip through to a real DB write.
        from app.core.config import settings
        monkeypatch.setattr(settings, "VISUAL_TELEMETRY_ENABLED", False)
        with patch("app.api.v1.endpoints.journeys.record_visual_event") as mock_record:
            r = client.post(
                "/api/v1/journeys/j1/steps/s1/visual/events",
                json={"eventType": "visual_impression", "vloId": "vlo-1", "sessionId": "sess-1", "eventData": {}},
            )
        assert r.status_code == 202
        assert r.json() == {"status": "disabled"}
        mock_record.assert_not_called()

    def test_enabled_records_event(self, client, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "VISUAL_TELEMETRY_ENABLED", True)
        with patch("app.api.v1.endpoints.journeys.record_visual_event") as mock_record:
            r = client.post(
                "/api/v1/journeys/j1/steps/s1/visual/events",
                json={"eventType": "visual_completed", "vloId": "vlo-1", "sessionId": "sess-1",
                      "eventData": {"durationMs": 4200}},
            )
        assert r.status_code == 202
        assert r.json() == {"status": "recorded"}
        mock_record.assert_called_once()
        event = mock_record.call_args.args[0]
        assert event.courseId == "j1"
        assert event.lessonId == "s1"
        assert event.userId == TEST_UID

    def test_write_failure_is_swallowed(self, client, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "VISUAL_TELEMETRY_ENABLED", True)
        with patch("app.api.v1.endpoints.journeys.record_visual_event", side_effect=RuntimeError("db down")):
            r = client.post(
                "/api/v1/journeys/j1/steps/s1/visual/events",
                json={"eventType": "visual_error", "vloId": "vlo-1", "sessionId": "sess-1", "eventData": {}},
            )
        assert r.status_code == 202

    def test_requires_auth(self):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.post(
                "/api/v1/journeys/j1/steps/s1/visual/events",
                json={"eventType": "visual_impression", "vloId": "vlo-1", "sessionId": "sess-1", "eventData": {}},
            )
        assert r.status_code in (401, 403)
