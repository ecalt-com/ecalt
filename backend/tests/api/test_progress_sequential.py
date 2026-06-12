"""
API tests for sequential step completion + quiz gating (phases 2–3, journey UX overhaul).

POST /api/v1/progress/{journey_id}/{step_id}
  - First step → 200 (quiz passed)
  - Later step with all prior steps done → 200
  - Later step with prior steps missing → 409 + missing_step_ids
  - Quiz not passed → 412 quiz_not_passed
  - Unknown journey → 200 (permissive, legacy links keep working; no quiz gate)
  - Idempotent re-complete → 200
  - No auth → 401
"""
from contextlib import contextmanager, ExitStack
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TEST_UID

STEPS = [
    {"id": "s1", "title": "Step 1", "type": "concept", "estimated_minutes": 10},
    {"id": "s2", "title": "Step 2", "type": "practice", "estimated_minutes": 10},
    {"id": "s3", "title": "Step 3", "type": "challenge", "estimated_minutes": 10},
]
TAGS = ["testing"]


@pytest.fixture
def client():
    """TestClient with auth wired to TEST_UID."""
    from app.main import app
    from app.core.auth import get_required_user, get_optional_user

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_required_user] = lambda: TEST_UID
    app.dependency_overrides[get_optional_user] = lambda: TEST_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture
def anon_client():
    """TestClient with no auth overrides — real auth rejects unauthenticated requests."""
    from app.main import app

    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


def progress_db(completed_step_ids, fresh_insert=True):
    """get_db mock for the progress module.

    fetchall → the user's existing user_progress rows (the order check),
    fetchone → the INSERT … RETURNING row (None simulates ON CONFLICT DO NOTHING).
    """
    @contextmanager
    def _get_db():
        cur = MagicMock()
        cur.fetchall.return_value = [{"step_id": s} for s in completed_step_ids]
        cur.fetchone.return_value = {"completed_at": "2026-06-11"} if fresh_insert else None
        cur.__enter__ = lambda s: cur
        cur.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cur
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)

        yield conn

    return _get_db


@contextmanager
def patched_progress(completed_step_ids, steps=(STEPS, TAGS), fresh_insert=True, quiz_passed=True):
    patches = (
        patch("app.api.v1.endpoints.progress._journey_steps", return_value=steps),
        patch("app.api.v1.endpoints.progress.get_db", progress_db(completed_step_ids, fresh_insert)),
        patch("app.api.v1.endpoints.progress.credit_step_knowledge"),
        patch("app.api.v1.endpoints.progress.step_quiz_passed", return_value=quiz_passed),
    )
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield


class TestSequentialCompletion:
    def test_first_step_always_completes(self, client):
        with patched_progress([]):
            r = client.post("/api/v1/progress/j1/s1")
        assert r.status_code == 200
        assert r.json()["completed"] is True

    def test_next_step_after_previous_done(self, client):
        with patched_progress(["s1"]):
            r = client.post("/api/v1/progress/j1/s2")
        assert r.status_code == 200

    def test_skipping_ahead_returns_409_with_missing_ids(self, client):
        with patched_progress([]):
            r = client.post("/api/v1/progress/j1/s3")
        assert r.status_code == 409
        detail = r.json()["detail"]
        assert detail["message"] == "previous_steps_incomplete"
        assert detail["missing_step_ids"] == ["s1", "s2"]

    def test_gap_in_middle_returns_409(self, client):
        # User has s1 grandfathered — a new step after a gap reports only the
        # genuinely missing ones.
        with patched_progress(["s1"]):
            r = client.post("/api/v1/progress/j1/s3")
        assert r.status_code == 409
        assert r.json()["detail"]["missing_step_ids"] == ["s2"]

    def test_unknown_journey_is_permissive(self, client):
        with patched_progress([], steps=None, quiz_passed=False):
            r = client.post("/api/v1/progress/deleted-journey/s9")
        assert r.status_code == 200

    def test_recomplete_is_idempotent(self, client):
        with patched_progress(["s1"], fresh_insert=False):
            r = client.post("/api/v1/progress/j1/s1")
        assert r.status_code == 200
        assert r.json()["completed_at"] is None

    def test_no_auth_returns_401(self, anon_client):
        r = anon_client.post("/api/v1/progress/j1/s1")
        assert r.status_code == 401


class TestQuizGate:
    def test_quiz_not_passed_returns_412(self, client):
        with patched_progress([], quiz_passed=False):
            r = client.post("/api/v1/progress/j1/s1")
        assert r.status_code == 412
        assert r.json()["detail"]["message"] == "quiz_not_passed"

    def test_quiz_passed_completes(self, client):
        with patched_progress(["s1"], quiz_passed=True):
            r = client.post("/api/v1/progress/j1/s2")
        assert r.status_code == 200

    def test_order_check_runs_before_quiz_gate(self, client):
        # Skipping ahead reports 409 even when the quiz is also unpassed,
        # so the client always learns about the sequence problem first.
        with patched_progress([], quiz_passed=False):
            r = client.post("/api/v1/progress/j1/s3")
        assert r.status_code == 409

    def test_unknown_step_in_known_journey_skips_quiz_gate(self, client):
        with patched_progress([], quiz_passed=False):
            r = client.post("/api/v1/progress/j1/not-a-step")
        assert r.status_code == 200
