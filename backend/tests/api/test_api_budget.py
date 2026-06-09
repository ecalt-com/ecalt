"""
API-level integration tests for budget enforcement.

Tests the HTTP layer: correct status codes, response shapes, and that
budget/coupon logic is wired to the right endpoints.

Endpoints covered:
  POST /api/v1/chat/stream
    - Budget ok → 200 (streaming)
    - Free trial message limit hit → 402 free_trial_exhausted
    - Token budget hit → 402 budget_exhausted
    - No auth → 401

  POST /api/v1/explore
    - Budget ok → 200
    - Budget exhausted → 402
    - No auth → 401

  GET /api/v1/journeys/{id}/steps/{step_id}/content
    - Cache hit → 200 (no budget check)
    - Cache miss + budget ok → 200
    - Cache miss + budget exhausted → 402
    - No auth → 401

  POST /api/v1/coupons/apply
    - Valid code → 200
    - Code not found → 400
    - Already redeemed → 400
    - Inactive coupon → 400
    - No auth → 401

  GET /api/v1/subscriptions/me
    - Returns total_budget_cents (plan + coupon credits)
    - Returns correct is_limited flag
    - Returns coupon_extras
"""
from unittest.mock import patch, MagicMock, AsyncMock
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FREE_TRIAL, INDIVIDUAL, usage, extras, TEST_UID, mock_db


# ── App setup ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """TestClient with auth wired to TEST_UID."""
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
    """TestClient with no auth overrides — real auth rejects unauthenticated requests."""
    from app.main import app

    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/chat/stream
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatStream:

    def test_budget_exhausted_returns_402_free_trial(self, client):
        with patch(
            "app.api.v1.endpoints.chat.check_budget",
            return_value=(False, "free_trial_exhausted"),
        ):
            res = client.post("/api/v1/chat/stream", json={"message": "hello"})

        assert res.status_code == 402
        body = res.json()
        assert body["detail"]["error"] == "free_trial_exhausted"
        assert "upgrade_url" in body["detail"]

    def test_budget_exhausted_returns_402_paid(self, client):
        with patch(
            "app.api.v1.endpoints.chat.check_budget",
            return_value=(False, "budget_exhausted"),
        ):
            res = client.post("/api/v1/chat/stream", json={"message": "hello"})

        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "budget_exhausted"

    def test_upgrade_url_present_in_402(self, client):
        with patch(
            "app.api.v1.endpoints.chat.check_budget",
            return_value=(False, "free_trial_exhausted"),
        ):
            res = client.post("/api/v1/chat/stream", json={"message": "hello"})

        assert res.json()["detail"]["upgrade_url"] == "/pricing"

    def test_empty_message_returns_422(self, client):
        # Pydantic min_length=1 validation
        res = client.post("/api/v1/chat/stream", json={"message": ""})
        assert res.status_code == 422

    def test_no_auth_returns_401(self, anon_client):
        res = anon_client.post("/api/v1/chat/stream", json={"message": "hello"})
        assert res.status_code == 401

    def test_budget_ok_calls_stream_chat(self, client):
        async def fake_stream():
            yield b'data: {"type":"start","conversation_id":"abc"}\n\n'
            yield b'data: {"type":"done"}\n\n'

        with patch("app.api.v1.endpoints.chat.check_budget", return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.chat.stream_chat", return_value=fake_stream()):
            res = client.post("/api/v1/chat/stream", json={"message": "hello"})

        assert res.status_code == 200

    def test_custom_interaction_type_passed_to_stream_chat(self, client):
        """
        Regression: interaction_type was dropped and hardcoded to 'daily_chat' in
        _post_stream_bg. Verify the endpoint forwards what the caller sends.
        """
        captured = {}

        async def fake_stream(uid, user_message, conversation_id=None, interaction_type="daily_chat"):
            captured["interaction_type"] = interaction_type
            yield b'data: {"type":"done"}\n\n'

        with patch("app.api.v1.endpoints.chat.check_budget", return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.chat.stream_chat", side_effect=fake_stream):
            client.post("/api/v1/chat/stream",
                        json={"message": "hello", "interaction_type": "onboarding"})

        assert captured.get("interaction_type") == "onboarding", \
            "interaction_type must be forwarded to stream_chat, not defaulted to daily_chat"


class TestChatServiceInteractionTypeThreading:
    """Unit tests for the interaction_type threading fix in chat_service.py."""

    def test_post_stream_bg_uses_passed_interaction_type(self):
        """_post_stream_bg must pass interaction_type through to record_usage, not hardcode it."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        recorded = []

        async def run():
            from app.services.chat_service import _post_stream_bg
            # Both record_usage and extract_knowledge_nodes are locally imported inside
            # _post_stream_bg — patch at the source module, not at chat_service.
            with patch("app.services.subscription_service.record_usage",
                       side_effect=lambda uid, in_t, out_t, model,
                       interaction_type="daily_chat", **kw: recorded.append(interaction_type)), \
                 patch("app.services.knowledge_service.extract_knowledge_nodes",
                       new_callable=AsyncMock), \
                 patch("app.services.fingerprint_service.get_fingerprint",
                       return_value=None, create=True):
                await _post_stream_bg(
                    uid=TEST_UID,
                    conv_id="conv-1",
                    user_message="hi",
                    assistant_response="hello",
                    model="gpt-4o-mini",
                    input_tokens=100,
                    output_tokens=50,
                    cached_input_tokens=0,
                    interaction_type="onboarding",
                )

        asyncio.run(run())
        assert recorded == ["onboarding"], \
            f"Expected 'onboarding' but got {recorded} — interaction_type was not threaded through"

    def test_post_stream_bg_defaults_to_daily_chat(self):
        """Without explicit interaction_type, default is 'daily_chat'."""
        import asyncio
        from unittest.mock import patch, AsyncMock

        recorded = []

        async def run():
            from app.services.chat_service import _post_stream_bg
            with patch("app.services.subscription_service.record_usage",
                       side_effect=lambda uid, in_t, out_t, model,
                       interaction_type="daily_chat", **kw: recorded.append(interaction_type)), \
                 patch("app.services.knowledge_service.extract_knowledge_nodes",
                       new_callable=AsyncMock):
                await _post_stream_bg(
                    uid=TEST_UID,
                    conv_id="conv-1",
                    user_message="hi",
                    assistant_response="hello",
                    model="gpt-4o-mini",
                    input_tokens=100,
                    output_tokens=50,
                )

        asyncio.run(run())
        assert recorded == ["daily_chat"]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/explore
# ═══════════════════════════════════════════════════════════════════════════════

class TestExplore:

    def test_budget_exhausted_returns_402(self, client):
        with patch(
            "app.api.v1.endpoints.explore.check_budget",
            return_value=(False, "budget_exhausted"),
        ):
            res = client.post("/api/v1/explore", json={"question": "How does gravity work?"})

        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "budget_exhausted"

    def test_free_trial_exhausted_returns_402(self, client):
        with patch(
            "app.api.v1.endpoints.explore.check_budget",
            return_value=(False, "free_trial_exhausted"),
        ):
            res = client.post("/api/v1/explore", json={"question": "What is DNA?"})

        assert res.status_code == 402

    def test_no_auth_returns_401(self, anon_client):
        res = anon_client.post("/api/v1/explore", json={"question": "Test?"})
        assert res.status_code == 401

    def test_empty_question_returns_400(self, client):
        with patch("app.api.v1.endpoints.explore.check_budget", return_value=(True, "ok")):
            res = client.post("/api/v1/explore", json={"question": "   "})
        assert res.status_code == 400

    def test_budget_ok_records_usage_after_generation(self, client):
        from app.models.schemas import Journey, JourneyStep
        from datetime import datetime, timezone

        fake_journey = Journey(
            id="fake-journey-id",
            question="Test?",
            title="Test Journey",
            description="A test",
            age_group="all",
            difficulty="beginner",
            estimated_hours=1.0,
            steps=[],
            tags=[],
            icon="🔬",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        usage_recorded = []
        def fake_record(uid, in_tok, out_tok, model, **kwargs):
            usage_recorded.append((uid, in_tok, out_tok, model))

        with patch("app.api.v1.endpoints.explore.check_budget", return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.explore.generate_journey",
                   new_callable=AsyncMock, return_value=(fake_journey, 100, 200)), \
             patch("app.api.v1.endpoints.explore.record_usage", side_effect=fake_record), \
             patch("app.api.v1.endpoints.explore.warm_journey_steps", new_callable=AsyncMock), \
             patch("app.api.v1.endpoints.explore.get_db", mock_db(None)):
            res = client.post("/api/v1/explore", json={"question": "Test question"})

        assert res.status_code == 200
        assert len(usage_recorded) == 1
        uid, in_tok, out_tok, model = usage_recorded[0]
        assert uid == TEST_UID
        assert in_tok == 100
        assert out_tok == 200


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/journeys/{id}/steps/{step_id}/content
# ═══════════════════════════════════════════════════════════════════════════════

class TestJourneyStepContent:

    JOURNEY_ID = "journey-rockets"
    STEP_ID    = "r-3"
    URL = f"/api/v1/journeys/{JOURNEY_ID}/steps/{STEP_ID}/content"

    def test_no_auth_returns_401(self, anon_client):
        res = anon_client.get(self.URL)
        assert res.status_code == 401

    def test_cache_hit_returns_200_without_budget_check(self, client):
        """Cached content is served for free — no budget check."""
        cached_row = {"content": "cached lesson content here"}

        check_budget_mock = MagicMock(return_value=(True, "ok"))

        with patch("app.api.v1.endpoints.journeys.get_db", mock_db(cached_row)), \
             patch("app.api.v1.endpoints.journeys.check_budget", check_budget_mock):
            res = client.get(self.URL)

        assert res.status_code == 200
        check_budget_mock.assert_not_called()

    def test_cache_miss_budget_exhausted_returns_402(self, client):
        """Cache miss triggers budget check — exhausted budget → 402."""
        with patch("app.api.v1.endpoints.journeys.get_db", mock_db(None)), \
             patch("app.api.v1.endpoints.journeys.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.get(self.URL)

        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "budget_exhausted"

    def test_cache_miss_free_trial_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.journeys.get_db", mock_db(None)), \
             patch("app.api.v1.endpoints.journeys.check_budget",
                   return_value=(False, "free_trial_exhausted")):
            res = client.get(self.URL)

        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "free_trial_exhausted"

    def test_cache_miss_budget_ok_calls_generate_and_records_usage(self, client):
        """On cache miss with budget ok: generates content, records usage, stores in cache."""
        usage_recorded = []

        def fake_record(uid, in_tok, out_tok, model, **kwargs):
            usage_recorded.append((uid, in_tok, out_tok, model))

        with patch("app.api.v1.endpoints.journeys.get_db",         mock_db(None, None)), \
             patch("app.api.v1.endpoints.journeys.check_budget",    return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.journeys.record_usage",    side_effect=fake_record), \
             patch("app.api.v1.endpoints.journeys.get_config",      return_value={"model": "gpt-4o-mini"}), \
             patch("app.api.v1.endpoints.journeys.generate_step_content",
                   new_callable=AsyncMock,
                   return_value=("lesson text here", 100, 200)):
            res = client.get(self.URL)

        assert res.status_code == 200
        data = res.json()
        assert data["content"] == "lesson text here"
        assert data["cached"] is False

        assert len(usage_recorded) == 1
        assert usage_recorded[0][0] == TEST_UID

    def test_cache_hit_does_not_record_usage(self, client):
        """Cached responses should never record usage — they cost nothing."""
        usage_recorded = []

        def fake_record(*args, **kwargs):
            usage_recorded.append(args)

        with patch("app.api.v1.endpoints.journeys.get_db",      mock_db({"content": "cached"})), \
             patch("app.api.v1.endpoints.journeys.record_usage", side_effect=fake_record):
            res = client.get(self.URL)

        assert res.status_code == 200
        assert res.json()["cached"] is True
        assert len(usage_recorded) == 0

    def test_402_response_includes_upgrade_url(self, client):
        with patch("app.api.v1.endpoints.journeys.get_db", mock_db(None)), \
             patch("app.api.v1.endpoints.journeys.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.get(self.URL)

        assert res.json()["detail"]["upgrade_url"] == "/pricing"


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/v1/coupons/apply
# ═══════════════════════════════════════════════════════════════════════════════

class TestCouponApplyEndpoint:

    def test_valid_coupon_returns_200(self, client):
        result = {
            "code": "PROMO10",
            "description": "10 cents credit",
            "credit_cents": 10.0,
            "bonus_messages": 0,
            "plan_override": None,
            "credit_expires_at": None,
        }
        with patch("app.api.v1.endpoints.coupons.apply_coupon", return_value=result):
            res = client.post("/api/v1/coupons/apply", json={"code": "PROMO10"})

        assert res.status_code == 200
        assert res.json()["code"] == "PROMO10"
        assert res.json()["credit_cents"] == 10.0

    def test_invalid_code_returns_400(self, client):
        with patch("app.api.v1.endpoints.coupons.apply_coupon",
                   side_effect=ValueError("Coupon not found.")):
            res = client.post("/api/v1/coupons/apply", json={"code": "NOPE"})

        assert res.status_code == 400
        assert "not found" in res.json()["detail"].lower()

    def test_already_redeemed_returns_400(self, client):
        with patch("app.api.v1.endpoints.coupons.apply_coupon",
                   side_effect=ValueError("You have already used this coupon.")):
            res = client.post("/api/v1/coupons/apply", json={"code": "USED"})

        assert res.status_code == 400
        assert "already used" in res.json()["detail"].lower()

    def test_inactive_coupon_returns_400(self, client):
        with patch("app.api.v1.endpoints.coupons.apply_coupon",
                   side_effect=ValueError("This coupon is no longer active.")):
            res = client.post("/api/v1/coupons/apply", json={"code": "OFF"})

        assert res.status_code == 400

    def test_no_auth_returns_401(self, anon_client):
        res = anon_client.post("/api/v1/coupons/apply", json={"code": "PROMO"})
        assert res.status_code == 401

    def test_expired_coupon_returns_400(self, client):
        with patch("app.api.v1.endpoints.coupons.apply_coupon",
                   side_effect=ValueError("This coupon has expired.")):
            res = client.post("/api/v1/coupons/apply", json={"code": "OLD"})

        assert res.status_code == 400
        assert "expired" in res.json()["detail"].lower()

    def test_max_uses_reached_returns_400(self, client):
        with patch("app.api.v1.endpoints.coupons.apply_coupon",
                   side_effect=ValueError("This coupon has reached its maximum number of uses.")):
            res = client.post("/api/v1/coupons/apply", json={"code": "FULL"})

        assert res.status_code == 400
        assert "maximum" in res.json()["detail"].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/subscriptions/me — budget fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestSubscriptionMe:

    def _me_row(self, plan, cost, coupon_credits=0.0, coupon_msgs=0, msg_count=0):
        """Build a fake _ME_QUERY result row matching what _build_me_response expects."""
        row = dict(plan)
        row["_usage_input_tokens"]  = 0
        row["_usage_output_tokens"] = 0
        row["_usage_cost_cents"]    = cost
        row["_usage_message_count"] = 1
        row["_extra_credits_cents"] = coupon_credits
        row["_bonus_messages"]      = coupon_msgs
        row["_is_admin"]            = False
        row["_lifetime_messages"]   = msg_count
        return row

    def _get_me(self, client, plan, cost, coupon_credits=0.0, coupon_msgs=0, msg_count=0):
        row = self._me_row(plan, cost, coupon_credits, coupon_msgs, msg_count)
        with patch("app.api.v1.endpoints.subscriptions.get_db", mock_db(row)):
            return client.get("/api/v1/subscriptions/me")

    def test_total_budget_includes_coupon_credits(self, client):
        res = self._get_me(client, FREE_TRIAL, cost=0.0, coupon_credits=10.0)
        assert res.status_code == 200
        # 20 (plan) + 10 (coupon) = 30
        assert res.json()["total_budget_cents"] == 30.0

    def test_is_limited_false_when_under_budget(self, client):
        res = self._get_me(client, FREE_TRIAL, cost=10.0)
        assert res.status_code == 200
        assert res.json()["is_limited"] is False

    def test_is_limited_true_when_ai_budget_exhausted(self, client):
        res = self._get_me(client, FREE_TRIAL, cost=20.0)  # at free trial limit
        assert res.json()["is_limited"] is True

    def test_is_limited_true_when_message_limit_hit(self, client):
        res = self._get_me(client, FREE_TRIAL, cost=0.0, msg_count=6)
        assert res.json()["is_limited"] is True

    def test_is_limited_false_after_coupon_restores_budget(self, client):
        # cost = 20 (exhausted plan budget), coupon = 10 → total = 30 → not limited
        res = self._get_me(client, FREE_TRIAL, cost=20.0, coupon_credits=10.0)
        assert res.json()["is_limited"] is False

    def test_coupon_extras_returned_in_response(self, client):
        res = self._get_me(client, FREE_TRIAL, cost=0.0, coupon_credits=50.0, coupon_msgs=5)
        body = res.json()
        assert body["coupon_extras"]["extra_credits_cents"] == 50.0
        assert body["coupon_extras"]["bonus_messages"] == 5

    def test_lifetime_limit_extended_by_coupon(self, client):
        # Plan limit 6 + coupon 10 bonus_messages = 16
        res = self._get_me(client, FREE_TRIAL, cost=0.0, coupon_msgs=10, msg_count=0)
        assert res.json()["lifetime_message_limit"] == 16

    def test_paid_plan_no_lifetime_message_limit(self, client):
        res = self._get_me(client, INDIVIDUAL, cost=0.0)
        assert res.json()["lifetime_message_limit"] is None

    def test_paid_plan_total_budget_correct(self, client):
        res = self._get_me(client, INDIVIDUAL, cost=0.0)
        assert res.json()["total_budget_cents"] == 760.0


# ═══════════════════════════════════════════════════════════════════════════════
# Admin coupon endpoints
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdminCouponEndpoints:

    def test_list_coupons_returns_200(self, client):
        with patch("app.api.v1.endpoints.coupons.list_coupons", return_value=[]):
            res = client.get("/api/v1/coupons/admin")
        assert res.status_code == 200
        assert "coupons" in res.json()

    def test_create_coupon_returns_coupon_object(self, client):
        created = {
            "code": "NEW10",
            "description": "New coupon",
            "credit_cents": 10.0,
            "bonus_messages": 0,
            "plan_override": None,
            "duration_days": None,
            "max_redemptions": None,
            "redemption_count": 0,
            "expires_at": None,
            "is_active": True,
            "created_at": "2026-05-18T10:00:00+00:00",
        }
        with patch("app.api.v1.endpoints.coupons.create_coupon", return_value=created):
            res = client.post("/api/v1/coupons/admin", json={
                "code": "NEW10",
                "description": "New coupon",
                "credit_cents": 10.0,
            })
        assert res.status_code == 200
        assert res.json()["code"] == "NEW10"

    def test_deactivate_coupon(self, client):
        updated = {"code": "OLD", "is_active": False, "description": "old"}
        with patch("app.api.v1.endpoints.coupons.update_coupon", return_value=updated):
            res = client.patch("/api/v1/coupons/admin/OLD", json={"is_active": False})
        assert res.status_code == 200
        assert res.json()["is_active"] is False

    def test_get_redemptions(self, client):
        with patch("app.api.v1.endpoints.coupons.get_coupon_redemptions", return_value=[]):
            res = client.get("/api/v1/coupons/admin/PROMO10/redemptions")
        assert res.status_code == 200
        assert "redemptions" in res.json()

    def test_no_auth_admin_returns_401(self, anon_client):
        res = anon_client.get("/api/v1/coupons/admin")
        assert res.status_code == 401
