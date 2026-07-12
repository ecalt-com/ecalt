"""Jurisdiction-aware consent-age rules (parental accounts plan, Phase 0).

Product policy — deliberately stricter than most local laws because ECALT sells
in India, whose DPDP Act requires verifiable parental consent for all under-18s:

- HARD_FLOOR_AGE: below this there is no self-signup at all (parent-created
  managed accounts arrive in Phase 1 of the plan).
- Parental consent is required for ALL minors (< ADULT_AGE), everywhere.

The per-country digital-consent-age matrix is recorded on the user at consent
time and drives the verification tier selection in Phase 2.
"""
from datetime import date
from typing import Optional

CONSENT_POLICY_VERSION = "1.0"

HARD_FLOOR_AGE = 13
ADULT_AGE = 18

# Age below which a child cannot consent to data processing themselves.
# GDPR Art. 8 member-state derogations, plus the major non-EU jurisdictions.
DIGITAL_CONSENT_AGE: dict[str, int] = {
    # EU / EEA
    "AT": 14, "BE": 13, "BG": 14, "HR": 16, "CY": 14, "CZ": 15, "DK": 13,
    "EE": 13, "FI": 13, "FR": 15, "DE": 16, "GR": 15, "HU": 16, "IE": 16,
    "IT": 14, "LV": 13, "LT": 14, "LU": 16, "MT": 13, "NL": 16, "PL": 16,
    "PT": 13, "RO": 16, "SK": 16, "SI": 15, "ES": 14, "SE": 13,
    "IS": 13, "NO": 13, "LI": 16,
    # Rest of world
    "GB": 13,  # UK GDPR
    "US": 13,  # COPPA
    "IN": 18,  # DPDP Act 2023
    "BR": 18,  # LGPD (children's data)
    "KR": 14,
    "CN": 14,  # PIPL
}
DEFAULT_DIGITAL_CONSENT_AGE = 16


def digital_consent_age(country: Optional[str]) -> int:
    """Consent age for an ISO 3166-1 alpha-2 country code; safe default when unknown."""
    if not country:
        return DEFAULT_DIGITAL_CONSENT_AGE
    return DIGITAL_CONSENT_AGE.get(country.strip().upper(), DEFAULT_DIGITAL_CONSENT_AGE)


def age_from_birth(birth_year: int, birth_month: Optional[int] = None,
                   today: Optional[date] = None) -> int:
    """Age in whole years. Without a birth month, falls back to calendar-year
    difference (legacy behavior). With one, the birthday month must have fully
    passed to count — the conservative reading protects a child whose exact
    birthday we don't collect."""
    today = today or date.today()
    age = today.year - birth_year
    if birth_month and today.month <= birth_month:
        age -= 1
    return age


def is_hard_blocked(age: int) -> bool:
    """No self-signup below the hard floor (COPPA baseline)."""
    return age < HARD_FLOOR_AGE


def requires_parental_consent(age: int) -> bool:
    """Global product policy: every minor needs parental consent."""
    return age < ADULT_AGE


def required_verification_tier(country: Optional[str], age: int) -> str:
    """How strongly the consenting parent must be verified.

    - 'card':       card micro-verification (Stripe SetupIntent). Required for
                    under-13s everywhere (COPPA verifiable parental consent for
                    an AI-chat product) and for all minors in India (DPDP
                    requires a verified identity signal from the parent).
    - 'email_plus': consent link + delayed follow-up notice with an objection
                    path. Sufficient for 13+ teens elsewhere (COPPA does not
                    apply at 13+; GDPR asks for "reasonable efforts").
    - 'id':         third-party ID/age verification — reserved for Phase 2+
                    providers (Privo/Yoti/k-ID); never returned yet.
    """
    if is_hard_blocked(age):
        return "card"
    if country and country.strip().upper() == "IN":
        return "card"
    return "email_plus"
