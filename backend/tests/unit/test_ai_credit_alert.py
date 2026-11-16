"""Admin email alert when an AI provider account runs out of credits."""
from unittest.mock import AsyncMock

import pytest

from app.services import ai_alert_service
from app.services.ai_alert_service import (
    alert_credits_exhausted,
    is_credit_exhaustion,
    reset_cooldown,
)

OPENAI_EXHAUSTED = (
    "Error code: 429 - {'error': {'message': 'You have no credits remaining. "
    "Add credits to continue using the API.', 'type': 'insufficient_quota', "
    "'code': 'credit_balance_exhausted'}}"
)
ANTHROPIC_EXHAUSTED = (
    "Error code: 400 - {'error': {'type': 'invalid_request_error', 'message': "
    "'Your credit balance is too low to access the Anthropic API.'}}"
)
TRANSIENT_RATE_LIMIT = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for gpt-5-nano: "
    "Limit 200000 TPM.', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
)


@pytest.fixture(autouse=True)
def _fresh_cooldown():
    reset_cooldown()
    yield
    reset_cooldown()


ADMINS = [
    {"uid": "admin-1", "email": "one@ecalt.com"},
    {"uid": "admin-2", "email": "two@ecalt.com"},
]


@pytest.fixture
def send_mock(monkeypatch):
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr(ai_alert_service, "send_ai_credits_exhausted_email", mock)
    monkeypatch.setattr(ai_alert_service, "_get_admin_recipients", lambda: list(ADMINS))
    return mock


# ── Detection ────────────────────────────────────────────────────────────────

def test_detects_openai_credit_exhaustion():
    assert is_credit_exhaustion(Exception(OPENAI_EXHAUSTED))


def test_detects_anthropic_credit_exhaustion():
    assert is_credit_exhaustion(Exception(ANTHROPIC_EXHAUSTED))


def test_ignores_transient_rate_limit():
    assert not is_credit_exhaustion(Exception(TRANSIENT_RATE_LIMIT))


def test_ignores_unrelated_errors():
    assert not is_credit_exhaustion(Exception("connection reset by peer"))


# ── Fan-out & cooldown ───────────────────────────────────────────────────────

async def test_alerts_every_admin(send_mock):
    await alert_credits_exhausted("openai", Exception(OPENAI_EXHAUSTED))
    assert send_mock.await_count == 2
    emails = {call.kwargs["admin_email"] for call in send_mock.await_args_list}
    assert emails == {"one@ecalt.com", "two@ecalt.com"}
    assert all(call.kwargs["provider"] == "openai" for call in send_mock.await_args_list)


async def test_second_alert_within_cooldown_is_suppressed(send_mock):
    await alert_credits_exhausted("openai", Exception(OPENAI_EXHAUSTED))
    await alert_credits_exhausted("openai", Exception(OPENAI_EXHAUSTED))
    assert send_mock.await_count == 2  # one email per admin, once


async def test_cooldown_is_per_provider(send_mock):
    await alert_credits_exhausted("openai", Exception(OPENAI_EXHAUSTED))
    await alert_credits_exhausted("anthropic", Exception(ANTHROPIC_EXHAUSTED))
    assert send_mock.await_count == 4


async def test_alert_never_raises(monkeypatch):
    monkeypatch.setattr(
        ai_alert_service, "_get_admin_recipients",
        lambda: (_ for _ in ()).throw(RuntimeError("db down")),
    )
    await alert_credits_exhausted("openai", Exception(OPENAI_EXHAUSTED))  # must not raise


async def test_error_detail_truncated(send_mock):
    await alert_credits_exhausted("openai", Exception(OPENAI_EXHAUSTED + "x" * 2000))
    detail = send_mock.await_args_list[0].kwargs["error_detail"]
    assert len(detail) <= 500


# ── provider_service hook ────────────────────────────────────────────────────

async def test_provider_hook_fires_only_on_credit_errors(monkeypatch):
    from app.services import provider_service

    mock = AsyncMock()
    monkeypatch.setattr(ai_alert_service, "alert_credits_exhausted", mock)

    await provider_service._maybe_alert_credits("openai", Exception(OPENAI_EXHAUSTED))
    assert mock.await_count == 1

    await provider_service._maybe_alert_credits("openai", Exception(TRANSIENT_RATE_LIMIT))
    assert mock.await_count == 1  # unchanged
