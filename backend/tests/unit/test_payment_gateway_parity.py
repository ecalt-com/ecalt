"""
Phase 4 — INR / USD payment gateway parity.

Verifies that a Razorpay (INR) subscriber on plan X gets the SAME token budget
and the SAME check_budget decisions as a Stripe (USD) subscriber on plan X.

The budget system is intentionally gateway-agnostic: get_user_plan() looks up
plan_configs by plan_id, which is identical regardless of payment_gateway.
These tests lock in that invariant.
"""
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    TEST_UID, mock_db, usage, extras,
    STUDENT, INDIVIDUAL, FAMILY,
    STUDENT_INR, INDIVIDUAL_INR, FAMILY_INR,
)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _run_check(plan, usage_val, extras_val, context="ai"):
    from app.services.subscription_service import check_budget
    with patch("app.services.subscription_service.get_user_plan",           return_value=plan), \
         patch("app.services.subscription_service.get_current_usage",        return_value=usage_val), \
         patch("app.services.subscription_service.get_coupon_extras",        return_value=extras_val), \
         patch("app.services.subscription_service.count_lifetime_messages",  return_value=0):
        return check_budget(TEST_UID, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# Budget decision parity
# ═══════════════════════════════════════════════════════════════════════════════

class TestGatewayBudgetParity:

    @pytest.mark.parametrize("usd_plan,inr_plan", [
        (STUDENT,    STUDENT_INR),
        (INDIVIDUAL, INDIVIDUAL_INR),
        (FAMILY,     FAMILY_INR),
    ])
    def test_both_gateways_allowed_at_zero_usage(self, usd_plan, inr_plan):
        allowed_usd, _ = _run_check(usd_plan, usage(0.0), extras())
        allowed_inr, _ = _run_check(inr_plan, usage(0.0), extras())
        assert allowed_usd is True
        assert allowed_inr is True

    @pytest.mark.parametrize("usd_plan,inr_plan", [
        (STUDENT,    STUDENT_INR),
        (INDIVIDUAL, INDIVIDUAL_INR),
        (FAMILY,     FAMILY_INR),
    ])
    def test_both_gateways_blocked_at_exact_budget(self, usd_plan, inr_plan):
        budget = usd_plan["token_budget_cents"]
        allowed_usd, reason_usd = _run_check(usd_plan, usage(budget), extras())
        allowed_inr, reason_inr = _run_check(inr_plan, usage(budget), extras())
        assert allowed_usd is False, f"USD {usd_plan['plan_id']} should block at {budget}¢"
        assert allowed_inr is False, f"INR {inr_plan['plan_id']} should block at {budget}¢"
        assert reason_usd == "budget_exhausted"
        assert reason_inr == "budget_exhausted"

    @pytest.mark.parametrize("usd_plan,inr_plan", [
        (STUDENT,    STUDENT_INR),
        (INDIVIDUAL, INDIVIDUAL_INR),
        (FAMILY,     FAMILY_INR),
    ])
    def test_both_gateways_allowed_just_under_budget(self, usd_plan, inr_plan):
        budget = usd_plan["token_budget_cents"]
        allowed_usd, _ = _run_check(usd_plan, usage(budget - 0.001), extras())
        allowed_inr, _ = _run_check(inr_plan, usage(budget - 0.001), extras())
        assert allowed_usd is True
        assert allowed_inr is True

    @pytest.mark.parametrize("usd_plan,inr_plan", [
        (STUDENT,    STUDENT_INR),
        (INDIVIDUAL, INDIVIDUAL_INR),
        (FAMILY,     FAMILY_INR),
    ])
    def test_coupon_credit_extends_budget_for_both_gateways(self, usd_plan, inr_plan):
        budget = usd_plan["token_budget_cents"]
        coupon = extras(credits=50.0)
        # At the base limit but with coupon credit — should be allowed
        allowed_usd, _ = _run_check(usd_plan, usage(budget), coupon)
        allowed_inr, _ = _run_check(inr_plan, usage(budget), coupon)
        assert allowed_usd is True
        assert allowed_inr is True

    @pytest.mark.parametrize("usd_plan,inr_plan", [
        (STUDENT,    STUDENT_INR),
        (INDIVIDUAL, INDIVIDUAL_INR),
        (FAMILY,     FAMILY_INR),
    ])
    def test_paid_chat_context_uses_token_budget_for_both(self, usd_plan, inr_plan):
        """Paid plans: chat context falls through to token budget gate (no message count)."""
        allowed_usd, reason_usd = _run_check(usd_plan, usage(1.0), extras(), context="chat")
        allowed_inr, reason_inr = _run_check(inr_plan, usage(1.0), extras(), context="chat")
        assert allowed_usd is True
        assert allowed_inr is True


# ═══════════════════════════════════════════════════════════════════════════════
# upsert_subscription_from_stripe preserves plan_id for both gateways
# ═══════════════════════════════════════════════════════════════════════════════

class TestSubscriptionUpsertGatewayNeutral:

    def _capture_insert(self):
        executed = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed.append((sql, params))
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        return capture_db, executed

    def test_stripe_upsert_stores_correct_plan_id(self):
        from app.services.subscription_service import upsert_subscription_from_stripe
        capture_db, rows = self._capture_insert()

        with patch("app.services.subscription_service.get_db", capture_db):
            upsert_subscription_from_stripe(
                uid=TEST_UID, plan_id="individual",
                stripe_subscription_id="sub_stripe_123",
                payment_gateway="stripe",
                status="active",
            )

        assert rows
        sql, params = rows[0]
        assert "INSERT INTO subscriptions" in sql
        assert params[1] == "individual"
        assert "stripe" in params

    def test_razorpay_upsert_stores_correct_plan_id(self):
        from app.services.subscription_service import upsert_subscription_from_stripe
        capture_db, rows = self._capture_insert()

        with patch("app.services.subscription_service.get_db", capture_db):
            upsert_subscription_from_stripe(
                uid=TEST_UID, plan_id="individual",
                payment_gateway="razorpay",
                razorpay_subscription_id="sub_rzp_456",
                status="active",
            )

        sql, params = rows[0]
        assert params[1] == "individual"
        assert "razorpay" in params

    def test_razorpay_and_stripe_produce_identical_plan_id_in_params(self):
        from app.services.subscription_service import upsert_subscription_from_stripe

        stripe_params = []
        razorpay_params = []

        @contextmanager
        def make_capture(store):
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, p=None: store.append(p)
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", lambda: make_capture(stripe_params)):
            upsert_subscription_from_stripe(TEST_UID, "student", payment_gateway="stripe")
        with patch("app.services.subscription_service.get_db", lambda: make_capture(razorpay_params)):
            upsert_subscription_from_stripe(TEST_UID, "student", payment_gateway="razorpay")

        # plan_id is position 1 in both cases
        assert stripe_params[0][1] == razorpay_params[0][1] == "student"
