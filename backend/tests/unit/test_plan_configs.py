"""
Phase 1 — Plan configuration integrity.

Verifies that:
- All plan fixtures have token_budget_cents consistent with the 40% rule.
- INR variants share the same plan_id and token_budget_cents as USD variants.
- The conftest fixture constants match the live DB (integration-only tests).
"""
import pytest

from tests.conftest import (
    FREE_TRIAL, STUDENT, INDIVIDUAL, FAMILY, UNIVERSITY, ENTERPRISE,
    STUDENT_INR, INDIVIDUAL_INR, FAMILY_INR,
)

ALL_PAID_PLANS = [STUDENT, INDIVIDUAL, FAMILY, UNIVERSITY, ENTERPRISE]
INR_PAIRS = [
    (STUDENT,     STUDENT_INR),
    (INDIVIDUAL,  INDIVIDUAL_INR),
    (FAMILY,      FAMILY_INR),
]


class TestFixtureInternalConsistency:

    def test_free_trial_has_token_budget(self):
        assert FREE_TRIAL["token_budget_cents"] == 20.0

    def test_free_trial_has_lifetime_message_limit(self):
        assert FREE_TRIAL["lifetime_message_limit"] == 6

    @pytest.mark.parametrize("plan", ALL_PAID_PLANS)
    def test_paid_plans_have_no_lifetime_message_limit(self, plan):
        assert plan["lifetime_message_limit"] is None, \
            f"{plan['plan_id']} should not have a lifetime message limit"

    @pytest.mark.parametrize("plan", ALL_PAID_PLANS)
    def test_paid_plans_are_active(self, plan):
        assert plan["is_active"] is True

    @pytest.mark.parametrize("plan", ALL_PAID_PLANS)
    def test_token_budget_is_positive(self, plan):
        assert plan["token_budget_cents"] > 0

    def test_budgets_increase_with_price(self):
        ordered = sorted(ALL_PAID_PLANS, key=lambda p: p["base_price_cents"])
        budgets = [p["token_budget_cents"] for p in ordered]
        assert budgets == sorted(budgets), \
            "Higher price plans must have higher token budgets"

    @pytest.mark.parametrize("plan", [STUDENT, INDIVIDUAL, FAMILY])
    def test_token_budget_is_between_50_and_90_percent_of_price(self, plan):
        ratio = plan["token_budget_cents"] / plan["base_price_cents"]
        assert 0.50 <= ratio <= 0.90, \
            f"{plan['plan_id']}: budget/price ratio {ratio:.2f} outside 50-90% band"


class TestINRUSDPlanParity:

    @pytest.mark.parametrize("usd_plan,inr_plan", INR_PAIRS)
    def test_same_plan_id(self, usd_plan, inr_plan):
        assert usd_plan["plan_id"] == inr_plan["plan_id"]

    @pytest.mark.parametrize("usd_plan,inr_plan", INR_PAIRS)
    def test_same_token_budget(self, usd_plan, inr_plan):
        assert usd_plan["token_budget_cents"] == inr_plan["token_budget_cents"], \
            f"INR and USD {usd_plan['plan_id']} must have identical token budgets"

    @pytest.mark.parametrize("usd_plan,inr_plan", INR_PAIRS)
    def test_inr_plan_has_razorpay_gateway(self, usd_plan, inr_plan):
        assert inr_plan.get("payment_gateway") == "razorpay"

    @pytest.mark.parametrize("usd_plan,inr_plan", INR_PAIRS)
    def test_inr_plan_has_paise_price(self, usd_plan, inr_plan):
        assert inr_plan.get("base_price_inr_paise", 0) > 0


@pytest.mark.integration
class TestFixturesMatchDB:
    """These run against the real DB — use `pytest -m integration` to include them."""

    def test_all_plan_token_budgets_match_db(self):
        from app.core.database import get_db
        fixtures = {p["plan_id"]: p for p in [FREE_TRIAL] + ALL_PAID_PLANS}

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT plan_id, token_budget_cents FROM plan_configs")
                rows = {r["plan_id"]: float(r["token_budget_cents"]) for r in cur.fetchall()}

        for plan_id, fixture in fixtures.items():
            assert plan_id in rows, f"plan_id '{plan_id}' missing from DB"
            assert fixture["token_budget_cents"] == rows[plan_id], \
                f"{plan_id}: fixture={fixture['token_budget_cents']} DB={rows[plan_id]}"

    def test_inr_plans_have_razorpay_plan_id_in_db(self):
        from app.core.database import get_db
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT plan_id, razorpay_plan_id FROM plan_configs "
                    "WHERE plan_id IN ('student', 'individual', 'family')"
                )
                rows = {r["plan_id"]: r["razorpay_plan_id"] for r in cur.fetchall()}

        for plan_id in ("student", "individual", "family"):
            assert rows.get(plan_id), f"{plan_id} missing razorpay_plan_id in DB"
