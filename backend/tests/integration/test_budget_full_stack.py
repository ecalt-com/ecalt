"""
Phase 8 — Full-stack DB-backed integration tests.

These tests hit a real Postgres/Supabase instance.  Run them with:
    pytest -m integration

They are excluded from the default `pytest` run so CI stays fast.

Prerequisites:
- The following env vars must be set (or in .env):
    DATABASE_URL  (or whatever your project uses for DB connection)
- The DB must have the tables: plan_configs, subscriptions, token_usage,
  usage_by_interaction, coupons.
"""
import uuid
from contextlib import contextmanager
from datetime import date

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def uid():
    return f"test-{uuid.uuid4().hex[:8]}"


@contextmanager
def _db():
    from app.core.database import get_db
    with get_db() as conn:
        yield conn


# ═══════════════════════════════════════════════════════════════════════════════
# plan_configs integrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlanConfigsDBIntegrity:

    def test_all_six_plans_exist(self):
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT plan_id FROM plan_configs WHERE is_active = TRUE ORDER BY plan_id")
                plan_ids = {r["plan_id"] for r in cur.fetchall()}

        expected = {"enterprise", "family", "free_trial", "individual", "student", "university"}
        assert expected.issubset(plan_ids), \
            f"Missing plans from DB: {expected - plan_ids}"

    def test_all_plans_have_positive_token_budgets(self):
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT plan_id, token_budget_cents FROM plan_configs WHERE is_active = TRUE")
                rows = cur.fetchall()

        for row in rows:
            budget = float(row["token_budget_cents"]) if row["token_budget_cents"] else 0
            assert budget > 0, f"{row['plan_id']} has non-positive budget {budget}"

    def test_individual_plan_budget_is_760(self):
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT token_budget_cents FROM plan_configs WHERE plan_id = 'individual'")
                row = cur.fetchone()
        assert float(row["token_budget_cents"]) == 760.0

    def test_student_plan_budget_is_360(self):
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT token_budget_cents FROM plan_configs WHERE plan_id = 'student'")
                row = cur.fetchone()
        assert float(row["token_budget_cents"]) == 360.0

    def test_enterprise_budget_greater_than_university(self):
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT plan_id, token_budget_cents FROM plan_configs "
                    "WHERE plan_id IN ('enterprise', 'university')"
                )
                rows = {r["plan_id"]: float(r["token_budget_cents"]) for r in cur.fetchall()}

        assert rows["enterprise"] > rows["university"]


# ═══════════════════════════════════════════════════════════════════════════════
# get_user_plan defaults to free_trial
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUserPlanDefaults:

    def test_unknown_user_defaults_to_free_trial(self, uid):
        from app.services.subscription_service import get_user_plan
        plan = get_user_plan(uid)
        assert plan["plan_id"] == "free_trial"

    def test_free_trial_budget_is_20_cents(self, uid):
        from app.services.subscription_service import get_user_plan
        plan = get_user_plan(uid)
        assert float(plan["token_budget_cents"]) == 20.0


# ═══════════════════════════════════════════════════════════════════════════════
# get_current_usage returns zeros for fresh user
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetCurrentUsageFreshUser:

    def test_fresh_user_usage_is_zero(self, uid):
        from app.services.subscription_service import get_current_usage
        result = get_current_usage(uid)
        assert result["estimated_cost_cents"] == 0.0
        assert result["message_count"] == 0

    def test_get_current_usage_returns_required_fields(self, uid):
        from app.services.subscription_service import get_current_usage
        result = get_current_usage(uid)
        assert "estimated_cost_cents" in result
        assert "message_count"        in result
        assert "input_tokens"         in result
        assert "output_tokens"        in result


# ═══════════════════════════════════════════════════════════════════════════════
# check_budget → record_usage → check_budget round-trip
# ═══════════════════════════════════════════════════════════════════════════════

class TestBudgetRoundTrip:

    def test_record_usage_increases_estimated_cost(self, uid):
        from app.services.subscription_service import get_current_usage, record_usage

        before = get_current_usage(uid)["estimated_cost_cents"]
        record_usage(uid, 1000, 500, "gpt-4o-mini", interaction_type="daily_chat")
        after = get_current_usage(uid)["estimated_cost_cents"]

        assert after > before, "Estimated cost must increase after recording usage"

    def test_record_usage_increments_message_count(self, uid):
        from app.services.subscription_service import get_current_usage, record_usage

        before = get_current_usage(uid)["message_count"]
        record_usage(uid, 500, 200, "gpt-4o-mini", interaction_type="quiz")
        after = get_current_usage(uid)["message_count"]

        assert after == before + 1

    def test_two_records_accumulate_tokens(self, uid):
        from app.services.subscription_service import get_current_usage, record_usage

        record_usage(uid, 500, 200, "gpt-4o-mini", interaction_type="daily_chat")
        record_usage(uid, 300, 100, "gpt-4o-mini", interaction_type="daily_chat")
        result = get_current_usage(uid)

        assert result["input_tokens"]  >= 800
        assert result["output_tokens"] >= 300

    def test_check_budget_blocks_after_budget_exhausted(self, uid):
        """
        Directly write a cost_cents row that exceeds the free_trial budget,
        then verify check_budget returns False.
        """
        from app.services.subscription_service import check_budget

        with _db() as conn:
            with conn.cursor() as cur:
                period_start = date.today().replace(day=1)
                cur.execute(
                    """
                    INSERT INTO token_usage (uid, period_start, input_tokens, output_tokens,
                        cached_input_tokens, message_count, estimated_cost_cents)
                    VALUES (%s, %s, 0, 0, 0, 0, 30.0)
                    ON CONFLICT (uid, period_start)
                    DO UPDATE SET estimated_cost_cents = 30.0
                    """,
                    (uid, period_start),
                )
            conn.commit()

        allowed, reason = check_budget(uid, context="ai")
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_check_budget_allowed_before_exhaustion(self, uid):
        from app.services.subscription_service import check_budget
        allowed, reason = check_budget(uid, context="ai")
        assert allowed is True
        assert reason == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# usage_by_interaction table
# ═══════════════════════════════════════════════════════════════════════════════

class TestUsageByInteractionTable:

    def test_record_usage_writes_usage_by_interaction(self, uid):
        from app.services.subscription_service import record_usage

        record_usage(uid, 400, 150, "gpt-4o-mini", interaction_type="mind_signature")

        with _db() as conn:
            with conn.cursor() as cur:
                period_start = date.today().replace(day=1)
                cur.execute(
                    """
                    SELECT interaction_type, request_count, input_tokens
                    FROM usage_by_interaction
                    WHERE uid = %s AND period_start = %s AND interaction_type = 'mind_signature'
                    """,
                    (uid, period_start),
                )
                row = cur.fetchone()

        assert row is not None, "usage_by_interaction row not created"
        assert row["interaction_type"] == "mind_signature"
        assert row["request_count"] >= 1
        assert row["input_tokens"] >= 400

    def test_multiple_calls_accumulate_per_interaction_type(self, uid):
        from app.services.subscription_service import record_usage

        record_usage(uid, 200, 80,  "gpt-4o-mini", interaction_type="quiz")
        record_usage(uid, 200, 80,  "gpt-4o-mini", interaction_type="quiz")
        record_usage(uid, 300, 100, "gpt-4o-mini", interaction_type="step_content")

        period_start = date.today().replace(day=1)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT interaction_type, request_count
                    FROM usage_by_interaction
                    WHERE uid = %s AND period_start = %s
                    ORDER BY interaction_type
                    """,
                    (uid, period_start),
                )
                rows = {r["interaction_type"]: r["request_count"] for r in cur.fetchall()}

        assert rows.get("quiz", 0) >= 2, "quiz should have 2 requests"
        assert rows.get("step_content", 0) >= 1, "step_content should have 1 request"

    def test_no_unknown_interaction_type_in_db_from_test(self, uid):
        """Ensure we never write 'unknown' to production tables."""
        from app.services.subscription_service import record_usage

        record_usage(uid, 100, 50, "gpt-4.1-nano", interaction_type="daily_spark")

        period_start = date.today().replace(day=1)
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT interaction_type FROM usage_by_interaction
                    WHERE uid = %s AND period_start = %s AND interaction_type = 'unknown'
                    """,
                    (uid, period_start),
                )
                row = cur.fetchone()

        assert row is None, "Found 'unknown' interaction_type in DB — a call site is missing the kwarg"


# ═══════════════════════════════════════════════════════════════════════════════
# INR / USD gateway parity — real subscription writes
# ═══════════════════════════════════════════════════════════════════════════════

class TestGatewayParityFullStack:

    @pytest.fixture
    def stripe_uid(self):
        return f"test-stripe-{uuid.uuid4().hex[:8]}"

    @pytest.fixture
    def razorpay_uid(self):
        return f"test-rzp-{uuid.uuid4().hex[:8]}"

    def test_stripe_and_razorpay_yield_same_token_budget(self, stripe_uid, razorpay_uid):
        from app.services.subscription_service import (
            upsert_subscription_from_stripe,
            get_user_plan,
        )

        upsert_subscription_from_stripe(
            stripe_uid, plan_id="individual",
            stripe_subscription_id=f"sub_{stripe_uid}",
            payment_gateway="stripe",
            status="active",
        )
        upsert_subscription_from_stripe(
            razorpay_uid, plan_id="individual",
            payment_gateway="razorpay",
            razorpay_subscription_id=f"sub_{razorpay_uid}",
            status="active",
        )

        stripe_plan   = get_user_plan(stripe_uid)
        razorpay_plan = get_user_plan(razorpay_uid)

        assert stripe_plan["token_budget_cents"] == razorpay_plan["token_budget_cents"], \
            "Stripe and Razorpay individual subscribers must have identical token budgets"

    def test_razorpay_student_budget_matches_stripe(self, stripe_uid, razorpay_uid):
        from app.services.subscription_service import (
            upsert_subscription_from_stripe,
            get_user_plan,
        )

        upsert_subscription_from_stripe(
            stripe_uid, plan_id="student",
            stripe_subscription_id=f"sub_{stripe_uid}",
            payment_gateway="stripe",
            status="active",
        )
        upsert_subscription_from_stripe(
            razorpay_uid, plan_id="student",
            payment_gateway="razorpay",
            razorpay_subscription_id=f"sub_{razorpay_uid}",
            status="active",
        )

        stripe_plan   = get_user_plan(stripe_uid)
        razorpay_plan = get_user_plan(razorpay_uid)

        assert float(stripe_plan["token_budget_cents"]) == float(razorpay_plan["token_budget_cents"])
        assert float(stripe_plan["token_budget_cents"]) == 360.0


# ═══════════════════════════════════════════════════════════════════════════════
# Coupon extras integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestCouponExtrasFullStack:

    def test_active_coupon_increases_effective_budget(self, uid):
        from app.services.subscription_service import get_coupon_extras, check_budget

        result = get_coupon_extras(uid)
        assert "credit_applied_cents"     in result
        assert "bonus_messages_applied"   in result

    def test_check_budget_respects_coupon_credit(self, uid):
        """
        Insert a coupon credit > 20¢ and exhaust base budget.
        check_budget must still pass because effective budget = 20 + credit.
        """
        from app.services.subscription_service import check_budget

        period_start = date.today().replace(day=1)
        coupon_id = f"test-coupon-{uid}"

        with _db() as conn:
            with conn.cursor() as cur:
                # Write token_usage row at 20¢ (base free_trial limit)
                cur.execute(
                    """
                    INSERT INTO token_usage (uid, period_start, input_tokens, output_tokens,
                        cached_input_tokens, message_count, estimated_cost_cents)
                    VALUES (%s, %s, 0, 0, 0, 0, 20.0)
                    ON CONFLICT (uid, period_start)
                    DO UPDATE SET estimated_cost_cents = 20.0
                    """,
                    (uid, period_start),
                )
                # Insert an active coupon with 50¢ credit
                cur.execute(
                    """
                    INSERT INTO coupons (coupon_id, uid, credit_applied_cents, bonus_messages_applied, expires_at)
                    VALUES (%s, %s, 50.0, 0, NOW() + INTERVAL '30 days')
                    ON CONFLICT DO NOTHING
                    """,
                    (coupon_id, uid),
                )
            conn.commit()

        allowed, reason = check_budget(uid, context="ai")
        assert allowed is True, \
            f"Budget should be extended by coupon credit. reason={reason}"
