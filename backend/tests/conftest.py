"""
Shared fixtures and helpers for the ECALT test suite.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest


# ── Plan fixtures ──────────────────────────────────────────────────────────────

FREE_TRIAL = {
    "plan_id": "free_trial",
    "name": "Free Trial",
    "base_price_cents": 0,
    "token_budget_cents": 20.0,   # $0.20 in cents
    "lifetime_message_limit": 6,
    "max_seats": 1,
    "is_active": True,
}

INDIVIDUAL = {
    "plan_id": "individual",
    "name": "Individual",
    "base_price_cents": 1000,
    "token_budget_cents": 760.0,
    "lifetime_message_limit": None,
    "max_seats": 1,
    "is_active": True,
}

STUDENT = {
    "plan_id": "student",
    "name": "Student",
    "base_price_cents": 500,
    "token_budget_cents": 360.0,
    "lifetime_message_limit": None,
    "max_seats": 1,
    "is_active": True,
}

FAMILY = {
    "plan_id": "family",
    "name": "Family",
    "base_price_cents": 3000,
    "token_budget_cents": 1560.0,
    "lifetime_message_limit": None,
    "max_seats": 5,
    "is_active": True,
}

UNIVERSITY = {
    "plan_id": "university",
    "name": "University",
    "base_price_cents": 29900,
    "token_budget_cents": 11960.0,
    "lifetime_message_limit": None,
    "max_seats": 50,
    "is_active": True,
}

ENTERPRISE = {
    "plan_id": "enterprise",
    "name": "Enterprise",
    "base_price_cents": 49900,
    "token_budget_cents": 19900.0,
    "lifetime_message_limit": None,
    "max_seats": 200,
    "is_active": True,
}

INDIVIDUAL_INR = {**INDIVIDUAL, "payment_gateway": "razorpay", "base_price_inr_paise": 69900}
STUDENT_INR    = {**STUDENT,    "payment_gateway": "razorpay", "base_price_inr_paise": 39900}
FAMILY_INR     = {**FAMILY,     "payment_gateway": "razorpay", "base_price_inr_paise": 199900}

# ── Usage fixtures ─────────────────────────────────────────────────────────────

def usage(cost_cents: float = 0.0, message_count: int = 0) -> dict:
    return {
        "uid": "test-uid",
        "estimated_cost_cents": cost_cents,
        "message_count": message_count,
        "input_tokens": 0,
        "output_tokens": 0,
    }


def extras(credits: float = 0.0, messages: int = 0) -> dict:
    return {"extra_credits_cents": credits, "bonus_messages": messages}


# ── Mock DB builder ────────────────────────────────────────────────────────────

def mock_db(*fetchone_returns):
    """
    Returns a mock get_db() context manager whose cursors will return
    fetchone_returns[0], [1], [2]… on successive fetchone() calls across
    any number of get_db() context entries.

    Usage:
        with patch('app.services.xxx.get_db', mock_db(row1, row2)):
            result = my_function()
    """
    # Shared iterator so successive get_db() calls advance through the list
    shared = iter(fetchone_returns)

    @contextmanager
    def _get_db():
        cur = MagicMock()
        cur.fetchone.side_effect = shared          # pops from shared iterator
        cur.__enter__ = lambda s: cur
        cur.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cur
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)

        yield conn

    return _get_db


def mock_db_fetchall(*fetchall_returns):
    """Like mock_db but for fetchall(). Returns lists in sequence."""
    shared = iter(fetchall_returns)

    @contextmanager
    def _get_db():
        cur = MagicMock()
        cur.fetchall.side_effect = shared
        cur.__enter__ = lambda s: cur
        cur.__exit__ = MagicMock(return_value=False)

        conn = MagicMock()
        conn.cursor.return_value = cur
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)

        yield conn

    return _get_db


# ── Auth override for API tests ───────────────────────────────────────────────

TEST_UID = "test-uid-123"
TEST_ADMIN_UID = "admin-uid-456"
