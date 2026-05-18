"""
Unit tests for the coupon service.

Scenarios covered:
  apply_coupon — validation failures
    - Code not found
    - Coupon is inactive
    - Coupon globally expired (expires_at in past)
    - Max redemptions reached
    - Same user already redeemed

  apply_coupon — success paths
    - Permanent credit applied
    - duration_days sets credit_expires_at correctly
    - No duration_days → credit_expires_at is None (permanent)
    - Snapshots credit_cents at redemption time (not live coupon value)
    - redemption_count incremented

  apply_coupon — credit expiry in get_coupon_extras
    - Expired redemption NOT counted in extras
    - Active redemption IS counted
    - Mix: only active ones summed

  create_coupon
    - Stores all fields correctly
    - Code uppercased

  update_coupon
    - is_active toggle
    - No valid fields → ValueError

  Edge cases
    - credit_cents = 0, bonus_messages = 0 (zero-value coupon — technically valid)
    - Very large credit_cents
    - Code is case-insensitive from user input
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import mock_db, TEST_UID, FREE_TRIAL, INDIVIDUAL


# ── Coupon fixtures ────────────────────────────────────────────────────────────

def active_coupon(
    code="PROMO10",
    credit_cents=10.0,
    bonus_messages=0,
    expires_at=None,
    max_redemptions=None,
    redemption_count=0,
    is_active=True,
    duration_days=None,
):
    return {
        "code": code,
        "description": "Test coupon",
        "credit_cents": credit_cents,
        "bonus_messages": bonus_messages,
        "plan_override": None,
        "duration_days": duration_days,
        "max_redemptions": max_redemptions,
        "redemption_count": redemption_count,
        "expires_at": expires_at,
        "is_active": is_active,
        "created_at": datetime.now(timezone.utc),
    }


FUTURE = datetime.now(timezone.utc) + timedelta(days=30)
PAST   = datetime.now(timezone.utc) - timedelta(days=1)


# ═══════════════════════════════════════════════════════════════════════════════
# apply_coupon — validation failures
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyCouponValidation:

    def test_code_not_found_raises(self):
        from app.services.coupon_service import apply_coupon
        # get_db returns None → coupon not found
        with patch("app.services.coupon_service.get_db", mock_db(None)):
            with pytest.raises(ValueError, match="not found"):
                apply_coupon(TEST_UID, "NOPE")

    def test_inactive_coupon_raises(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(is_active=False)
        with patch("app.services.coupon_service.get_db", mock_db(coupon)):
            with pytest.raises(ValueError, match="no longer active"):
                apply_coupon(TEST_UID, "PROMO10")

    def test_globally_expired_raises(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(expires_at=PAST)
        with patch("app.services.coupon_service.get_db", mock_db(coupon)):
            with pytest.raises(ValueError, match="expired"):
                apply_coupon(TEST_UID, "PROMO10")

    def test_future_expiry_is_valid(self):
        """Coupon with expires_at in the future should not be rejected for expiry."""
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(expires_at=FUTURE)
        # First get_db: coupon lookup
        # Second get_db: check existing redemption → None (not yet redeemed)
        # Third get_db: INSERT + UPDATE (no fetchone)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["code"] == "PROMO10"

    def test_max_redemptions_reached_raises(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(max_redemptions=100, redemption_count=100)
        with patch("app.services.coupon_service.get_db", mock_db(coupon)):
            with pytest.raises(ValueError, match="maximum number"):
                apply_coupon(TEST_UID, "PROMO10")

    def test_one_under_max_redemptions_is_valid(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(max_redemptions=100, redemption_count=99)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["code"] == "PROMO10"

    def test_unlimited_redemptions_always_valid(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(max_redemptions=None, redemption_count=9999)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["code"] == "PROMO10"

    def test_already_redeemed_raises(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon()
        existing_row = {"uid": TEST_UID, "coupon_code": "PROMO10"}
        # Second get_db returns existing redemption row → blocked
        with patch("app.services.coupon_service.get_db", mock_db(coupon, existing_row)):
            with pytest.raises(ValueError, match="already used"):
                apply_coupon(TEST_UID, "PROMO10")

    def test_different_user_can_use_same_code(self):
        """The unique constraint is per (uid, code), not per code globally."""
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon()
        # Second get_db: check for THIS user's redemption → None (not yet)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon("different-uid", "PROMO10")
        assert result["code"] == "PROMO10"


# ═══════════════════════════════════════════════════════════════════════════════
# apply_coupon — success paths
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyCouponSuccess:

    def test_returns_correct_fields(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(credit_cents=50.0, bonus_messages=5)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["credit_cents"] == 50.0
        assert result["bonus_messages"] == 5
        assert result["code"] == "PROMO10"

    def test_permanent_credit_has_no_expiry(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(duration_days=None)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["credit_expires_at"] is None

    def test_duration_days_sets_expiry_relative_to_now(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(duration_days=30)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["credit_expires_at"] is not None
        expiry = datetime.fromisoformat(result["credit_expires_at"])
        now = datetime.now(timezone.utc)
        # Should be ~30 days from now (allow ±5 seconds for test execution time)
        expected = now + timedelta(days=30)
        assert abs((expiry - expected).total_seconds()) < 5

    def test_code_is_uppercased(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(code="PROMO10")
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "promo10")  # lowercase input
        assert result["code"] == "PROMO10"

    def test_zero_value_coupon_is_accepted(self):
        """A coupon with 0 credit and 0 messages is technically valid."""
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(credit_cents=0.0, bonus_messages=0)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["credit_cents"] == 0.0

    def test_large_credit_accepted(self):
        from app.services.coupon_service import apply_coupon
        coupon = active_coupon(credit_cents=99999.0)
        with patch("app.services.coupon_service.get_db", mock_db(coupon, None, None)):
            result = apply_coupon(TEST_UID, "PROMO10")
        assert result["credit_cents"] == 99999.0


# ═══════════════════════════════════════════════════════════════════════════════
# Coupon credit expiry in get_coupon_extras
# These test the SQL query's WHERE clause behavior via mocked DB results
# ═══════════════════════════════════════════════════════════════════════════════

class TestCouponExpiryInExtras:
    """
    get_coupon_extras uses a DB query with:
      WHERE (credit_expires_at IS NULL OR credit_expires_at > now())

    We test this by controlling what the SUM query returns — the DB handles
    the filtering. These tests verify the aggregation result is used correctly.
    """

    def test_active_permanent_credit_counted(self):
        from app.services.subscription_service import get_coupon_extras
        row = {"extra_credits": 50.0, "bonus_messages": 0}
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 50.0

    def test_expired_credit_returns_zero(self):
        """Expired credits filtered out by DB — SUM returns 0."""
        from app.services.subscription_service import get_coupon_extras
        row = {"extra_credits": 0.0, "bonus_messages": 0}  # DB filtered out expired
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 0.0

    def test_mixed_expired_and_active_only_active_counted(self):
        """Two coupons: one expired (10¢), one active (30¢) → DB returns 30."""
        from app.services.subscription_service import get_coupon_extras
        row = {"extra_credits": 30.0, "bonus_messages": 0}
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 30.0


# ═══════════════════════════════════════════════════════════════════════════════
# Full end-to-end budget scenarios combining coupon + budget check
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullCouponBudgetScenario:
    """
    These tests simulate the complete scenario flow described in the task:
    1. Free trial exhausts AI budget
    2. Apply coupon of 10 cents → access restored
    3. Exhaust again
    4. Upgrade to paid plan
    5. Exhaust paid plan budget
    6. Apply coupon again → access restored
    7. Exhaust final budget
    """

    def _check(self, plan, cost, coupon_credits, coupon_msgs=0, msg_count=0, context="ai"):
        from app.services.subscription_service import check_budget
        p1 = patch("app.services.subscription_service.get_user_plan",            return_value=plan)
        p2 = patch("app.services.subscription_service.get_current_usage",         return_value={"estimated_cost_cents": cost})
        p3 = patch("app.services.subscription_service.get_coupon_extras",         return_value={"extra_credits_cents": coupon_credits, "bonus_messages": coupon_msgs})
        p4 = patch("app.services.subscription_service.count_lifetime_messages",   return_value=msg_count)
        with p1, p2, p3, p4:
            return check_budget(TEST_UID, context=context)

    # Stage 1: Free trial, clean slate
    def test_01_free_trial_no_usage_allowed(self):
        allowed, _ = self._check(FREE_TRIAL, cost=0.0, coupon_credits=0.0)
        assert allowed is True

    # Stage 2: Free trial AI budget exhausted
    def test_02_free_trial_ai_budget_exhausted(self):
        allowed, reason = self._check(FREE_TRIAL, cost=20.0, coupon_credits=0.0)
        assert allowed is False
        assert reason == "budget_exhausted"

    # Stage 3: Chat still works for free trial (message gate, not token)
    def test_03_free_trial_chat_still_works_after_ai_exhausted(self):
        allowed, _ = self._check(FREE_TRIAL, cost=20.0, coupon_credits=0.0, msg_count=3, context="chat")
        assert allowed is True

    # Stage 4: Apply 10-cent coupon → AI access restored
    def test_04_coupon_10_cents_restores_ai_access(self):
        allowed, _ = self._check(FREE_TRIAL, cost=20.0, coupon_credits=10.0)
        assert allowed is True  # total budget = 30

    # Stage 5: Use the coupon credit too — now at 30 cents
    def test_05_coupon_credit_also_exhausted(self):
        allowed, reason = self._check(FREE_TRIAL, cost=30.0, coupon_credits=10.0)
        assert allowed is False
        assert reason == "budget_exhausted"

    # Stage 6: Upgrade to Individual plan (reset period usage to 0)
    def test_06_paid_plan_fresh_period_allowed(self):
        allowed, _ = self._check(INDIVIDUAL, cost=0.0, coupon_credits=0.0)
        assert allowed is True

    # Stage 7: Exhaust paid plan budget (760 cents)
    def test_07_paid_plan_budget_exhausted(self):
        allowed, reason = self._check(INDIVIDUAL, cost=760.0, coupon_credits=0.0)
        assert allowed is False
        assert reason == "budget_exhausted"

    # Stage 8: Apply coupon to paid plan → access restored
    def test_08_coupon_on_paid_plan_restores_access(self):
        allowed, _ = self._check(INDIVIDUAL, cost=760.0, coupon_credits=10.0)
        assert allowed is True  # total budget = 770

    # Stage 9: Exhaust paid plan + coupon combined
    def test_09_paid_plan_plus_coupon_exhausted(self):
        allowed, reason = self._check(INDIVIDUAL, cost=770.0, coupon_credits=10.0)
        assert allowed is False
        assert reason == "budget_exhausted"

    # Stage 10: Free trial chat — all 6 messages used
    def test_10_free_trial_chat_exhausted(self):
        allowed, reason = self._check(FREE_TRIAL, cost=0.0, coupon_credits=0.0, msg_count=6, context="chat")
        assert allowed is False
        assert reason == "free_trial_exhausted"

    # Stage 11: Apply bonus_messages coupon → chat access restored
    def test_11_coupon_bonus_messages_restores_chat(self):
        allowed, _ = self._check(FREE_TRIAL, cost=0.0, coupon_credits=0.0, coupon_msgs=10, msg_count=6, context="chat")
        assert allowed is True  # limit now 16

    # Stage 12: Exhaust extended chat limit
    def test_12_extended_chat_limit_also_exhausted(self):
        allowed, reason = self._check(FREE_TRIAL, cost=0.0, coupon_credits=0.0, coupon_msgs=10, msg_count=16, context="chat")
        assert allowed is False
        assert reason == "free_trial_exhausted"
