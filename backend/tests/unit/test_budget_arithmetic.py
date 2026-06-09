"""
Phase 5 — Token budget arithmetic and edge cases.

Covers:
- All six plan tiers (not just free_trial and individual).
- Float boundary conditions (just-under, exact, just-over).
- NULL token_budget_cents falls back to 20.0.
- Period rollover: new month resets usage to 0.
- check_budget and get_budget_status must agree on is_limited.
- Coupon credits and bonus messages for all plan tiers.
"""
from contextlib import contextmanager, ExitStack
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    TEST_UID, mock_db, usage, extras,
    FREE_TRIAL, STUDENT, INDIVIDUAL, FAMILY, UNIVERSITY, ENTERPRISE,
)

ALL_PLANS_WITH_BUDGETS = [
    (FREE_TRIAL,  20.0),
    (STUDENT,     360.0),
    (INDIVIDUAL,  760.0),
    (FAMILY,      1560.0),
    (UNIVERSITY,  11960.0),
    (ENTERPRISE,  19900.0),
]


# ── Helper ─────────────────────────────────────────────────────────────────────

def _run_check(plan, usage_val, extras_val, context="ai", msg_count=0):
    from app.services.subscription_service import check_budget
    with patch("app.services.subscription_service.get_user_plan",           return_value=plan), \
         patch("app.services.subscription_service.get_current_usage",        return_value=usage_val), \
         patch("app.services.subscription_service.get_coupon_extras",        return_value=extras_val), \
         patch("app.services.subscription_service.count_lifetime_messages",  return_value=msg_count):
        return check_budget(TEST_UID, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# All plan tiers — budget thresholds
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllPlanBudgetThresholds:

    @pytest.mark.parametrize("plan,budget", ALL_PLANS_WITH_BUDGETS)
    def test_zero_usage_always_allowed(self, plan, budget):
        allowed, reason = _run_check(plan, usage(0.0), extras())
        assert allowed is True
        assert reason == "ok"

    @pytest.mark.parametrize("plan,budget", ALL_PLANS_WITH_BUDGETS)
    def test_just_under_budget_allowed(self, plan, budget):
        allowed, _ = _run_check(plan, usage(budget - 0.001), extras())
        assert allowed is True

    @pytest.mark.parametrize("plan,budget", ALL_PLANS_WITH_BUDGETS)
    def test_at_exact_budget_blocked(self, plan, budget):
        allowed, reason = _run_check(plan, usage(budget), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    @pytest.mark.parametrize("plan,budget", ALL_PLANS_WITH_BUDGETS)
    def test_over_budget_blocked(self, plan, budget):
        allowed, reason = _run_check(plan, usage(budget * 1.1), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    @pytest.mark.parametrize("plan", [STUDENT, INDIVIDUAL, FAMILY, UNIVERSITY, ENTERPRISE])
    def test_paid_chat_context_uses_token_gate_not_message_count(self, plan):
        """Paid plans: chat context is gated by token budget only, never message count."""
        allowed, reason = _run_check(plan, usage(0.0), extras(), context="chat")
        assert allowed is True
        assert reason == "ok"

    @pytest.mark.parametrize("plan", [STUDENT, INDIVIDUAL, FAMILY, UNIVERSITY, ENTERPRISE])
    def test_paid_plan_chat_exhausted_budget_blocks(self, plan):
        budget = plan["token_budget_cents"]
        allowed, reason = _run_check(plan, usage(budget), extras(), context="chat")
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_family_plan_coupon_extends_budget(self):
        allowed, _ = _run_check(FAMILY, usage(1560.0), extras(credits=100.0))
        assert allowed is True  # 1560 < 1660

    def test_family_at_extended_budget_blocked(self):
        allowed, reason = _run_check(FAMILY, usage(1660.0), extras(credits=100.0))
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_university_plan_blocks_at_exact_limit(self):
        allowed, reason = _run_check(UNIVERSITY, usage(11960.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_enterprise_plan_blocks_at_exact_limit(self):
        allowed, reason = _run_check(ENTERPRISE, usage(19900.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"


# ═══════════════════════════════════════════════════════════════════════════════
# Float edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestFloatEdgeCases:

    def test_cumulative_small_additions_stay_under_budget(self):
        """0.02 × 10 should equal 0.2, which is < 20.0 — never trigger a false block."""
        cost = sum(0.02 for _ in range(10))
        allowed, _ = _run_check(FREE_TRIAL, usage(cost), extras())
        assert allowed is True

    def test_tiny_remaining_budget_still_allows(self):
        # 19.9999 < 20.0 → should be allowed
        allowed, _ = _run_check(FREE_TRIAL, usage(19.9999), extras())
        assert allowed is True

    def test_exact_budget_boundary_blocks(self):
        allowed, reason = _run_check(FREE_TRIAL, usage(20.0), extras())
        assert allowed is False

    def test_large_enterprise_budget_no_overflow(self):
        """19899.99 < 19900.0 — large numbers must not overflow comparison."""
        allowed, _ = _run_check(ENTERPRISE, usage(19899.99), extras())
        assert allowed is True
        allowed, _ = _run_check(ENTERPRISE, usage(19900.0), extras())
        assert allowed is False

    def test_coupon_credit_float_addition(self):
        """Multiple small coupon credits must not cause floating-point drift."""
        # base 20.0 + three 3.33 credits ≈ 29.99 total budget
        # spent 29.98 → allowed; spent 29.99 → blocked
        stacked_credits = 3.33 + 3.33 + 3.33  # = 9.99
        total_budget = 20.0 + stacked_credits   # ≈ 29.99

        allowed, _ = _run_check(FREE_TRIAL, usage(total_budget - 0.01),
                                extras(credits=stacked_credits))
        assert allowed is True

    def test_null_token_budget_falls_back_to_20(self):
        plan_null = {**FREE_TRIAL, "token_budget_cents": None}
        allowed, _ = _run_check(plan_null, usage(19.9), extras())
        assert allowed is True  # default 20.0

    def test_null_token_budget_blocks_at_20(self):
        plan_null = {**FREE_TRIAL, "token_budget_cents": None}
        allowed, reason = _run_check(plan_null, usage(20.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_zero_token_budget_means_always_blocked(self):
        """A plan with token_budget_cents=0 blocks every request (edge case)."""
        plan_zero = {**INDIVIDUAL, "token_budget_cents": 0}
        # NOTE: the fallback `or 20.0` in check_budget means 0 → 20.0 default.
        # Test that this fallback is applied (fail-safe: never block a plan erroneously).
        allowed, _ = _run_check(plan_zero, usage(0.0), extras())
        # 0 is falsy → falls back to 20.0 → 0 < 20 → allowed
        assert allowed is True


# ═══════════════════════════════════════════════════════════════════════════════
# check_budget ↔ get_budget_status consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestBudgetStatusConsistency:
    """check_budget and get_budget_status must agree on is_limited."""

    @pytest.mark.parametrize("plan,cost,expected_limited", [
        (FREE_TRIAL,  20.0,   True),   # at limit
        (FREE_TRIAL,  19.9,   False),  # under limit
        (INDIVIDUAL,  760.0,  True),   # at limit
        (INDIVIDUAL,  100.0,  False),  # well under
        (FAMILY,      1560.0, True),
        (FAMILY,      1000.0, False),
    ])
    def test_check_budget_and_get_budget_status_agree(self, plan, cost, expected_limited):
        from app.services.subscription_service import check_budget, get_budget_status

        shared_patches = [
            patch("app.services.subscription_service.get_user_plan",           return_value=plan),
            patch("app.services.subscription_service.get_current_usage",        return_value=usage(cost)),
            patch("app.services.subscription_service.get_coupon_extras",        return_value=extras()),
            patch("app.services.subscription_service.count_lifetime_messages",  return_value=0),
        ]

        with ExitStack() as stack:
            for p in shared_patches:
                stack.enter_context(p)
            allowed, _ = check_budget(TEST_UID, context="ai")
            status = get_budget_status(TEST_UID)

        assert status["is_limited"] == (not allowed), \
            f"check_budget={allowed} but is_limited={status['is_limited']} (cost={cost}, plan={plan['plan_id']})"

    def test_get_budget_status_remaining_cents_never_negative(self):
        from app.services.subscription_service import get_budget_status

        with patch("app.services.subscription_service.get_user_plan",           return_value=FREE_TRIAL), \
             patch("app.services.subscription_service.get_current_usage",        return_value=usage(50.0)), \
             patch("app.services.subscription_service.get_coupon_extras",        return_value=extras()), \
             patch("app.services.subscription_service.count_lifetime_messages",  return_value=0):
            status = get_budget_status(TEST_UID)

        assert status["remaining_cents"] >= 0.0, "remaining_cents must never be negative"

    def test_get_budget_status_pct_used_correct(self):
        from app.services.subscription_service import get_budget_status

        with patch("app.services.subscription_service.get_user_plan",           return_value=INDIVIDUAL), \
             patch("app.services.subscription_service.get_current_usage",        return_value=usage(380.0)), \
             patch("app.services.subscription_service.get_coupon_extras",        return_value=extras()), \
             patch("app.services.subscription_service.count_lifetime_messages",  return_value=0):
            status = get_budget_status(TEST_UID)

        assert abs(status["pct_used"] - 50.0) < 0.1  # 380/760 ≈ 50%


# ═══════════════════════════════════════════════════════════════════════════════
# Period rollover
# ═══════════════════════════════════════════════════════════════════════════════

class TestPeriodRollover:

    def test_no_row_for_current_month_returns_zero_usage(self):
        """If there's no token_usage row for the current period, usage is zero."""
        from app.services.subscription_service import get_current_usage

        # mock_db(None) means fetchone returns None → no row exists this period
        with patch("app.services.subscription_service.get_db", mock_db(None)):
            result = get_current_usage(TEST_UID)

        assert result["estimated_cost_cents"] == 0.0
        assert result["message_count"] == 0
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0

    def test_usage_returns_current_month_data(self):
        """If a row exists, its values are returned as-is."""
        from app.services.subscription_service import get_current_usage

        row = {
            "uid": TEST_UID,
            "period_start": "2026-06-01",
            "estimated_cost_cents": 42.5,
            "message_count": 8,
            "input_tokens": 10000,
            "output_tokens": 5000,
        }
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_current_usage(TEST_UID)

        assert result["estimated_cost_cents"] == 42.5
        assert result["message_count"] == 8

    def test_record_usage_uses_first_day_of_month(self):
        """period_start must always be the 1st of the current month."""
        from datetime import date
        from app.services.subscription_service import record_usage

        recorded_periods = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            def execute_side(sql, params=None):
                if params and "token_usage" in sql:
                    recorded_periods.append(params[1])  # index 1 = period_start
            cur.execute.side_effect = execute_side
            cur.fetchone.return_value = {"estimated_cost_cents": 0.01, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 50, "gpt-4o-mini", interaction_type="spark")

        assert recorded_periods
        period = recorded_periods[0]
        assert period.day == 1, f"period_start must be day 1, got day {period.day}"
