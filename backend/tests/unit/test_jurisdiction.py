"""
Unit tests for the jurisdiction consent-age matrix and month-accurate age math.
"""
from datetime import date

from app.core.jurisdiction import (
    DEFAULT_DIGITAL_CONSENT_AGE,
    age_from_birth,
    digital_consent_age,
    is_hard_blocked,
    required_verification_tier,
    requires_parental_consent,
)


# ── Consent-age matrix ────────────────────────────────────────────────────────

def test_known_jurisdictions():
    assert digital_consent_age("US") == 13   # COPPA
    assert digital_consent_age("GB") == 13   # UK GDPR
    assert digital_consent_age("DE") == 16   # GDPR default, no derogation
    assert digital_consent_age("FR") == 15
    assert digital_consent_age("IN") == 18   # DPDP Act
    assert digital_consent_age("BR") == 18
    assert digital_consent_age("KR") == 14


def test_unknown_country_uses_safe_default():
    assert digital_consent_age("ZZ") == DEFAULT_DIGITAL_CONSENT_AGE
    assert digital_consent_age(None) == DEFAULT_DIGITAL_CONSENT_AGE
    assert digital_consent_age("") == DEFAULT_DIGITAL_CONSENT_AGE


def test_country_code_is_case_insensitive():
    assert digital_consent_age("us") == 13
    assert digital_consent_age(" in ") == 18


# ── Month-accurate age ────────────────────────────────────────────────────────

TODAY = date(2026, 7, 10)


def test_year_only_falls_back_to_calendar_difference():
    assert age_from_birth(2013, None, today=TODAY) == 13
    assert age_from_birth(2008, None, today=TODAY) == 18


def test_birthday_month_passed_counts_full_age():
    assert age_from_birth(2013, 6, today=TODAY) == 13  # June birthday, now July


def test_birthday_month_not_passed_is_conservative():
    assert age_from_birth(2013, 8, today=TODAY) == 12  # August birthday, now July


def test_current_month_is_treated_as_not_yet_attained():
    # We don't collect the day, so within the birthday month assume the
    # birthday hasn't happened yet — the stricter reading protects the child.
    assert age_from_birth(2013, 7, today=TODAY) == 12


# ── Policy helpers ────────────────────────────────────────────────────────────

def test_hard_floor():
    assert is_hard_blocked(12)
    assert not is_hard_blocked(13)


def test_parental_consent_required_for_all_minors():
    assert requires_parental_consent(13)
    assert requires_parental_consent(17)
    assert not requires_parental_consent(18)


# ── Verification tiers (Phase 2) ──────────────────────────────────────────────

def test_under_13_always_needs_card_verification():
    assert required_verification_tier("US", 10) == "card"
    assert required_verification_tier(None, 12) == "card"


def test_india_needs_card_for_all_minors():
    assert required_verification_tier("IN", 15) == "card"
    assert required_verification_tier("in", 17) == "card"


def test_teens_elsewhere_use_email_plus():
    assert required_verification_tier("US", 15) == "email_plus"
    assert required_verification_tier("DE", 16) == "email_plus"
    assert required_verification_tier(None, 14) == "email_plus"
