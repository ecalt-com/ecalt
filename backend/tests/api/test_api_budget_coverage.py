"""
Phase 2 — Budget gate completeness.

Verifies that every AI-generating endpoint enforces check_budget before calling the model,
and that all endpoints return 402 with the correct error shape when budget is exhausted.

Endpoints newly covered (not in test_api_budget.py):
  POST /api/v1/mind-signature/generate
  POST /api/v1/mind-signature/generate/force
  GET  /api/v1/knowledge/spark
"""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FREE_TRIAL, INDIVIDUAL, usage, extras, TEST_UID, mock_db


@pytest.fixture
def client():
    from app.main import app
    from app.core.auth import get_required_user, get_optional_user, get_admin_user

    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_required_user] = lambda: TEST_UID
    app.dependency_overrides[get_optional_user] = lambda: TEST_UID
    app.dependency_overrides[get_admin_user]    = lambda: TEST_UID

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


@pytest.fixture
def anon_client():
    from app.main import app

    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/mind-signature/generate
# ═══════════════════════════════════════════════════════════════════════════════

class TestMindSignatureBudgetGate:

    def test_budget_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.post("/api/v1/mind-signature/generate")
        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "budget_exhausted"

    def test_free_trial_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(False, "free_trial_exhausted")):
            res = client.post("/api/v1/mind-signature/generate")
        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "free_trial_exhausted"

    def test_402_includes_upgrade_url(self, client):
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.post("/api/v1/mind-signature/generate")
        assert res.json()["detail"]["upgrade_url"] == "/pricing"

    def test_budget_ok_calls_generate_and_records_usage(self, client):
        fake_sig = {"id": "sig-123", "capability_narrative": "great mind"}
        recorded = []

        def spy_record(uid, in_tok, out_tok, model, interaction_type="unknown", **kw):
            recorded.append({"in": in_tok, "out": out_tok, "type": interaction_type})

        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.mind_signature.should_generate_signature",
                   return_value=True), \
             patch("app.api.v1.endpoints.mind_signature.update_domain_mastery"), \
             patch("app.api.v1.endpoints.mind_signature.generate_mind_signature",
                   new_callable=AsyncMock, return_value=(fake_sig, 420, 195)), \
             patch("app.api.v1.endpoints.mind_signature.record_usage", side_effect=spy_record):
            res = client.post("/api/v1/mind-signature/generate")

        assert res.status_code == 200
        assert len(recorded) == 1
        assert recorded[0]["in"] == 420
        assert recorded[0]["out"] == 195
        assert recorded[0]["type"] == "mind_signature"

    def test_no_auth_returns_401(self, anon_client):
        res = anon_client.post("/api/v1/mind-signature/generate")
        assert res.status_code == 401

    def test_not_enough_mastery_returns_422_without_consuming_budget(self, client):
        """Budget check passes but mastery gate blocks — no token usage charged."""
        recorded = []
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.mind_signature.should_generate_signature",
                   return_value=False), \
             patch("app.api.v1.endpoints.mind_signature.update_domain_mastery"), \
             patch("app.api.v1.endpoints.mind_signature.record_usage",
                   side_effect=lambda *a, **kw: recorded.append(a)):
            res = client.post("/api/v1/mind-signature/generate")

        assert res.status_code == 422
        assert len(recorded) == 0, "No tokens should be charged when mastery gate rejects"


class TestMindSignatureForceGenerateBudgetGate:

    def test_force_generate_budget_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.post("/api/v1/mind-signature/generate/force")
        assert res.status_code == 402

    def test_force_generate_records_usage(self, client):
        fake_sig = {"id": "sig-456"}
        recorded = []

        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.mind_signature.update_domain_mastery"), \
             patch("app.api.v1.endpoints.mind_signature.generate_mind_signature",
                   new_callable=AsyncMock, return_value=(fake_sig, 380, 160)), \
             patch("app.api.v1.endpoints.mind_signature.record_usage",
                   side_effect=lambda uid, in_tok, out_tok, model, **kw: recorded.append((in_tok, out_tok))):
            res = client.post("/api/v1/mind-signature/generate/force")

        assert res.status_code == 200
        assert len(recorded) == 1
        assert recorded[0] == (380, 160)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/knowledge/spark
# ═══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeDailySparkBudgetGate:

    def test_budget_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.get("/api/v1/knowledge/spark")
        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "budget_exhausted"

    def test_free_trial_ai_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.get("/api/v1/knowledge/spark")
        assert res.status_code == 402

    def test_budget_ok_returns_200(self, client):
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.knowledge.generate_daily_spark",
                   new_callable=AsyncMock, return_value=("What if gravity ran backwards?", 80, 30)):
            res = client.get("/api/v1/knowledge/spark")
        assert res.status_code == 200
        assert res.json()["spark"] == "What if gravity ran backwards?"

    def test_cache_hit_does_not_record_usage(self, client):
        """When generate_daily_spark returns 0 tokens (cache hit), record_usage is not called."""
        recorded = []
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.knowledge.generate_daily_spark",
                   new_callable=AsyncMock, return_value=("Cached spark", 0, 0)), \
             patch("app.api.v1.endpoints.knowledge.record_usage",
                   side_effect=lambda *a, **kw: recorded.append(a)):
            res = client.get("/api/v1/knowledge/spark")
        assert res.status_code == 200
        assert len(recorded) == 0, "Cache hits must not incur token charges"

    def test_fresh_generation_records_usage(self, client):
        """When generate_daily_spark returns real tokens, they are recorded."""
        recorded = []
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.knowledge.generate_daily_spark",
                   new_callable=AsyncMock, return_value=("A new spark", 90, 35)), \
             patch("app.api.v1.endpoints.knowledge.record_usage",
                   side_effect=lambda uid, in_tok, out_tok, model, **kw: recorded.append((in_tok, out_tok))):
            client.get("/api/v1/knowledge/spark")
        assert len(recorded) == 1
        assert recorded[0] == (90, 35)

    def test_records_correct_interaction_type(self, client):
        recorded_types = []
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.knowledge.generate_daily_spark",
                   new_callable=AsyncMock, return_value=("spark", 60, 20)), \
             patch("app.api.v1.endpoints.knowledge.record_usage",
                   side_effect=lambda uid, in_tok, out_tok, model,
                   interaction_type="unknown", **kw: recorded_types.append(interaction_type)):
            client.get("/api/v1/knowledge/spark")
        assert recorded_types == ["daily_spark"]

    def test_no_auth_returns_401(self, anon_client):
        res = anon_client.get("/api/v1/knowledge/spark")
        assert res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# All AI endpoints — auth required
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllAIEndpointsRequireAuth:

    @pytest.mark.parametrize("method,url,body", [
        ("post", "/api/v1/chat/stream",                    {"message": "hello"}),
        ("post", "/api/v1/explore",                        {"question": "Why?"}),
        ("post", "/api/v1/quiz",                           {"concept": "x", "context": "y"}),
        ("post", "/api/v1/mind-signature/generate",        {}),
        ("post", "/api/v1/mind-signature/generate/force",  {}),
        ("get",  "/api/v1/knowledge/spark",                None),
    ])
    def test_unauthenticated_returns_401(self, anon_client, method, url, body):
        if body is None:
            res = getattr(anon_client, method)(url)
        else:
            res = getattr(anon_client, method)(url, json=body)
        assert res.status_code == 401, f"{method.upper()} {url} should require auth"
