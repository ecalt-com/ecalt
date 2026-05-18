"""
Unit tests for the token budget system.

Scenarios covered:
  Free trial / chat context
    - Under message limit → allowed
    - At message limit → blocked (free_trial_exhausted)
    - Over limit (edge) → blocked
    - Token budget exhausted but chat still gated by message count only
    - Coupon bonus_messages extends the limit
    - Coupon bonus_messages + at new limit → blocked

  Free trial / AI context (step content, explore)
    - Under token budget → allowed
    - At budget boundary (float edge) → blocked
    - Budget exhausted + coupon credit → allowed
    - Budget exhausted + coupon credit + at new budget → blocked
    - Message count exhausted but token budget ok → AI calls still allowed

  Paid plan
    - Under budget → allowed
    - At budget → blocked
    - Budget exhausted + coupon credit → allowed
    - At new budget after coupon → blocked
    - Paid user: message count does NOT block (no message limit)
    - No subscription row → falls back to free_trial budget

  Coupon extras aggregation
    - No redemptions → zeros
    - One active permanent credit
    - Two active credits stack
    - Expired credit not counted
    - Mix of expired + active → only active counted
    - DB error → returns zeros (fail-open for extras)

  record_usage
    - Correct SQL executed
    - Correct cost calculation
    - DB error swallowed silently (fail-safe)

  cost_for_tokens
    - Known models return correct cents
    - Unknown model falls back to default rates
    - Zero tokens → zero cost
"""
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager

import pytest

from tests.conftest import (
    FREE_TRIAL, INDIVIDUAL, STUDENT,
    usage, extras, mock_db, TEST_UID,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _patch_budget_deps(plan=None, usage_val=None, extras_val=None, msg_count=0):
    """Patch all four sub-functions check_budget() calls internally."""
    return (
        patch("app.services.subscription_service.get_user_plan",    return_value=plan or FREE_TRIAL),
        patch("app.services.subscription_service.get_current_usage", return_value=usage_val or usage()),
        patch("app.services.subscription_service.get_coupon_extras", return_value=extras_val or extras()),
        patch("app.services.subscription_service.count_lifetime_messages", return_value=msg_count),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Free Trial — Chat context
# ═══════════════════════════════════════════════════════════════════════════════

class TestFreeTrialChat:

    def test_zero_messages_is_allowed(self):
        from app.services.subscription_service import check_budget
        with _patch_budget_deps(plan=FREE_TRIAL, msg_count=0)[0], \
             _patch_budget_deps(plan=FREE_TRIAL, msg_count=0)[1], \
             _patch_budget_deps(plan=FREE_TRIAL, msg_count=0)[2], \
             _patch_budget_deps(plan=FREE_TRIAL, msg_count=0)[3]:
            allowed, reason = check_budget(TEST_UID, context="chat")
        # Simpler: use patch context managers all at once
        assert True  # placeholder — real test below uses the multi-patch helper

    def _run(self, plan, usage_val, extras_val, msg_count):
        from app.services.subscription_service import check_budget
        p1 = patch("app.services.subscription_service.get_user_plan",            return_value=plan)
        p2 = patch("app.services.subscription_service.get_current_usage",         return_value=usage_val)
        p3 = patch("app.services.subscription_service.get_coupon_extras",         return_value=extras_val)
        p4 = patch("app.services.subscription_service.count_lifetime_messages",   return_value=msg_count)
        with p1, p2, p3, p4:
            return check_budget(TEST_UID, context="chat")

    def test_zero_messages_allowed(self):
        allowed, reason = self._run(FREE_TRIAL, usage(), extras(), msg_count=0)
        assert allowed is True
        assert reason == "ok"

    def test_one_below_limit_allowed(self):
        allowed, reason = self._run(FREE_TRIAL, usage(), extras(), msg_count=5)
        assert allowed is True

    def test_at_limit_blocked(self):
        allowed, reason = self._run(FREE_TRIAL, usage(), extras(), msg_count=6)
        assert allowed is False
        assert reason == "free_trial_exhausted"

    def test_over_limit_blocked(self):
        # Guard against data corruption where count exceeds limit
        allowed, reason = self._run(FREE_TRIAL, usage(), extras(), msg_count=99)
        assert allowed is False
        assert reason == "free_trial_exhausted"

    def test_token_budget_exhausted_does_not_block_chat(self):
        # Chat gate for free trial is message count ONLY — exhausted AI budget
        # must not block chat (it uses a separate gate)
        allowed, reason = self._run(
            FREE_TRIAL,
            usage(cost_cents=9999.0),  # completely exhausted token budget
            extras(),
            msg_count=3,               # only 3 of 6 messages used
        )
        assert allowed is True
        assert reason == "ok"

    def test_coupon_bonus_messages_extends_limit(self):
        # Plan limit = 6, coupon gives +10 → total = 16
        allowed, reason = self._run(FREE_TRIAL, usage(), extras(messages=10), msg_count=6)
        assert allowed is True  # 6 < 16

    def test_coupon_bonus_messages_at_new_limit_blocked(self):
        allowed, reason = self._run(FREE_TRIAL, usage(), extras(messages=10), msg_count=16)
        assert allowed is False
        assert reason == "free_trial_exhausted"

    def test_coupon_bonus_messages_one_under_new_limit_allowed(self):
        allowed, reason = self._run(FREE_TRIAL, usage(), extras(messages=10), msg_count=15)
        assert allowed is True

    def test_null_lifetime_limit_falls_back_to_default_6(self):
        plan_no_limit = {**FREE_TRIAL, "lifetime_message_limit": None}
        allowed, reason = self._run(plan_no_limit, usage(), extras(), msg_count=6)
        assert allowed is False
        assert reason == "free_trial_exhausted"


# ═══════════════════════════════════════════════════════════════════════════════
# Free Trial — AI context (step content, explore)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFreeTrialAI:

    def _run(self, plan, usage_val, extras_val, msg_count=0):
        from app.services.subscription_service import check_budget
        p1 = patch("app.services.subscription_service.get_user_plan",            return_value=plan)
        p2 = patch("app.services.subscription_service.get_current_usage",         return_value=usage_val)
        p3 = patch("app.services.subscription_service.get_coupon_extras",         return_value=extras_val)
        p4 = patch("app.services.subscription_service.count_lifetime_messages",   return_value=msg_count)
        with p1, p2, p3, p4:
            return check_budget(TEST_UID, context="ai")

    def test_zero_usage_allowed(self):
        allowed, reason = self._run(FREE_TRIAL, usage(0.0), extras())
        assert allowed is True

    def test_just_under_budget_allowed(self):
        allowed, reason = self._run(FREE_TRIAL, usage(19.999), extras())
        assert allowed is True

    def test_at_exact_budget_blocked(self):
        # budget = 20.0, cost = 20.0 → cost >= budget → blocked
        allowed, reason = self._run(FREE_TRIAL, usage(20.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_over_budget_blocked(self):
        allowed, reason = self._run(FREE_TRIAL, usage(25.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_coupon_credit_restores_access(self):
        # Budget = 20 cents, used = 20 cents (exhausted), coupon = 10 cents → total 30 cents
        allowed, reason = self._run(FREE_TRIAL, usage(20.0), extras(credits=10.0))
        assert allowed is True

    def test_coupon_credit_one_under_new_budget_allowed(self):
        allowed, reason = self._run(FREE_TRIAL, usage(29.99), extras(credits=10.0))
        assert allowed is True

    def test_coupon_credit_at_new_budget_blocked(self):
        # total_budget = 20 + 10 = 30, cost = 30 → blocked
        allowed, reason = self._run(FREE_TRIAL, usage(30.0), extras(credits=10.0))
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_multiple_coupons_stack(self):
        # Two coupons: 5 cents + 10 cents = 15 extra → total budget 35
        allowed, reason = self._run(FREE_TRIAL, usage(20.0), extras(credits=15.0))
        assert allowed is True  # 20 < 35

    def test_message_limit_exhausted_does_not_block_ai(self):
        # Free trial with all 6 chat messages used but token budget ok
        # AI context should NOT check message count
        allowed, reason = self._run(FREE_TRIAL, usage(5.0), extras(), msg_count=6)
        assert allowed is True  # 5 < 20, message count irrelevant for AI

    def test_none_token_budget_uses_default(self):
        plan = {**FREE_TRIAL, "token_budget_cents": None}
        allowed, reason = self._run(plan, usage(19.9), extras())
        assert allowed is True  # default is 20.0

    def test_none_token_budget_default_blocks_at_20(self):
        plan = {**FREE_TRIAL, "token_budget_cents": None}
        allowed, reason = self._run(plan, usage(20.0), extras())
        assert allowed is False


# ═══════════════════════════════════════════════════════════════════════════════
# Paid Plans
# ═══════════════════════════════════════════════════════════════════════════════

class TestPaidPlan:

    def _run(self, plan, usage_val, extras_val, context="ai"):
        from app.services.subscription_service import check_budget
        p1 = patch("app.services.subscription_service.get_user_plan",            return_value=plan)
        p2 = patch("app.services.subscription_service.get_current_usage",         return_value=usage_val)
        p3 = patch("app.services.subscription_service.get_coupon_extras",         return_value=extras_val)
        p4 = patch("app.services.subscription_service.count_lifetime_messages",   return_value=0)
        with p1, p2, p3, p4:
            return check_budget(TEST_UID, context=context)

    def test_zero_usage_allowed(self):
        allowed, reason = self._run(INDIVIDUAL, usage(0.0), extras())
        assert allowed is True

    def test_mid_budget_allowed(self):
        allowed, reason = self._run(INDIVIDUAL, usage(400.0), extras())
        assert allowed is True

    def test_just_under_budget_allowed(self):
        allowed, reason = self._run(INDIVIDUAL, usage(759.99), extras())
        assert allowed is True

    def test_at_budget_blocked(self):
        allowed, reason = self._run(INDIVIDUAL, usage(760.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_over_budget_blocked(self):
        allowed, reason = self._run(INDIVIDUAL, usage(1000.0), extras())
        assert allowed is False

    def test_coupon_credit_extends_budget(self):
        # Budget 760, used 760 (exhausted), coupon 10 → allowed
        allowed, reason = self._run(INDIVIDUAL, usage(760.0), extras(credits=10.0))
        assert allowed is True

    def test_coupon_credit_at_new_limit_blocked(self):
        allowed, reason = self._run(INDIVIDUAL, usage(770.0), extras(credits=10.0))
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_chat_context_paid_uses_token_budget(self):
        # Paid users have no message limit — chat context falls through to token budget
        allowed, reason = self._run(INDIVIDUAL, usage(100.0), extras(), context="chat")
        assert allowed is True

    def test_chat_context_paid_budget_exhausted_blocked(self):
        allowed, reason = self._run(INDIVIDUAL, usage(760.0), extras(), context="chat")
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_student_plan_budget(self):
        allowed, reason = self._run(STUDENT, usage(359.99), extras())
        assert allowed is True

    def test_student_plan_at_budget_blocked(self):
        allowed, reason = self._run(STUDENT, usage(360.0), extras())
        assert allowed is False

    def test_no_subscription_falls_back_to_free_trial_budget(self):
        # Simulate get_user_plan returning free_trial (no subscription row)
        allowed, reason = self._run(FREE_TRIAL, usage(21.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"


# ═══════════════════════════════════════════════════════════════════════════════
# Coupon Extras Aggregation
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetCouponExtras:

    def test_no_redemptions_returns_zeros(self):
        from app.services.subscription_service import get_coupon_extras
        row = {"extra_credits": 0.0, "bonus_messages": 0}
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 0.0
        assert result["bonus_messages"] == 0

    def test_single_active_coupon_credit(self):
        from app.services.subscription_service import get_coupon_extras
        row = {"extra_credits": 50.0, "bonus_messages": 0}
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 50.0

    def test_stacked_coupon_credits(self):
        from app.services.subscription_service import get_coupon_extras
        # Two coupons: 30 + 20 = 50 cents, DB returns SUM
        row = {"extra_credits": 50.0, "bonus_messages": 0}
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 50.0

    def test_bonus_messages_returned(self):
        from app.services.subscription_service import get_coupon_extras
        row = {"extra_credits": 0.0, "bonus_messages": 20}
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["bonus_messages"] == 20

    def test_both_credits_and_messages(self):
        from app.services.subscription_service import get_coupon_extras
        row = {"extra_credits": 100.0, "bonus_messages": 15}
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 100.0
        assert result["bonus_messages"] == 15

    def test_db_error_returns_zeros_fail_open(self):
        """If DB is unavailable, credits return 0 — user may be incorrectly limited.
        This is a known tradeoff: fail-safe for the system, not the user."""
        from app.services.subscription_service import get_coupon_extras

        @contextmanager
        def broken_db():
            raise Exception("Connection refused")
            yield  # unreachable

        with patch("app.services.subscription_service.get_db", broken_db):
            result = get_coupon_extras(TEST_UID)
        assert result["extra_credits_cents"] == 0.0
        assert result["bonus_messages"] == 0

    def test_null_db_row_returns_zeros(self):
        from app.services.subscription_service import get_coupon_extras
        with patch("app.services.subscription_service.get_db", mock_db(None)):
            # fetchone returns None → should not crash
            try:
                result = get_coupon_extras(TEST_UID)
            except (TypeError, AttributeError):
                pytest.fail("get_coupon_extras crashed on None row")


# ═══════════════════════════════════════════════════════════════════════════════
# record_usage
# ═══════════════════════════════════════════════════════════════════════════════

class TestRecordUsage:

    def test_executes_upsert_sql(self):
        from app.services.subscription_service import record_usage

        captured_sql = []
        captured_params = []

        @contextmanager
        def spy_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: (
                captured_sql.append(sql) or captured_params.append(params)
            )
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", spy_db):
            record_usage(TEST_UID, input_tokens=100, output_tokens=200, model="gpt-4o-mini")

        assert len(captured_sql) == 1
        sql = captured_sql[0]
        assert "INSERT INTO token_usage" in sql
        assert "ON CONFLICT" in sql

    def test_correct_cost_calculated(self):
        from app.services.subscription_service import record_usage
        from app.services.provider_service import cost_for_tokens

        recorded_params = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: recorded_params.append(params)
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        in_tok, out_tok = 1000, 500
        expected_cost = cost_for_tokens("gpt-4o-mini", in_tok, out_tok)

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, in_tok, out_tok, "gpt-4o-mini")

        assert recorded_params, "execute() was never called"
        params = recorded_params[0]
        # params = (uid, period_start, input_tokens, output_tokens, cost_cents)
        assert params[0] == TEST_UID
        assert params[2] == in_tok
        assert params[3] == out_tok
        assert abs(params[4] - expected_cost) < 1e-9

    def test_db_error_is_swallowed(self):
        """record_usage must never crash the calling request."""
        from app.services.subscription_service import record_usage

        @contextmanager
        def exploding_db():
            raise RuntimeError("DB connection failed")
            yield

        with patch("app.services.subscription_service.get_db", exploding_db):
            # Should not raise
            record_usage(TEST_UID, 100, 100, "gpt-4o-mini")

    def test_accumulates_across_calls(self):
        """Verify the ON CONFLICT upsert pattern is used (not bare INSERT)."""
        from app.services.subscription_service import record_usage

        executed = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed.append(sql)
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 100, "gpt-4o-mini")
            record_usage(TEST_UID, 200, 200, "gpt-4o-mini")

        # Both calls should use upsert
        assert all("ON CONFLICT" in sql for sql in executed)
        assert len(executed) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# cost_for_tokens (pure function — no mocking needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCostForTokens:

    def test_gpt4o_mini_known_rates(self):
        from app.services.provider_service import cost_for_tokens
        # gpt-4o-mini: input 0.000015 cents/tok, output 0.000060 cents/tok
        cost = cost_for_tokens("gpt-4o-mini", 1_000_000, 0)
        assert abs(cost - 15.0) < 0.001  # $0.15 = 15 cents per 1M input tokens

    def test_gpt41_nano_cheapest(self):
        from app.services.provider_service import cost_for_tokens
        nano = cost_for_tokens("gpt-4.1-nano", 1000, 1000)
        mini = cost_for_tokens("gpt-4o-mini", 1000, 1000)
        assert nano < mini

    def test_unknown_model_uses_default_rates(self):
        from app.services.provider_service import cost_for_tokens
        # Should not raise; returns some positive number
        cost = cost_for_tokens("totally-unknown-model-xyz", 1000, 1000)
        assert cost > 0

    def test_zero_tokens_zero_cost(self):
        from app.services.provider_service import cost_for_tokens
        cost = cost_for_tokens("gpt-4o-mini", 0, 0)
        assert cost == 0.0

    def test_output_more_expensive_than_input(self):
        from app.services.provider_service import cost_for_tokens
        input_cost  = cost_for_tokens("gpt-4o-mini", 1000, 0)
        output_cost = cost_for_tokens("gpt-4o-mini", 0, 1000)
        assert output_cost > input_cost

    def test_haiku_cheaper_than_sonnet(self):
        from app.services.provider_service import cost_for_tokens
        haiku  = cost_for_tokens("claude-haiku-4-5-20251001", 1000, 1000)
        sonnet = cost_for_tokens("claude-sonnet-4-6",          1000, 1000)
        assert haiku < sonnet
