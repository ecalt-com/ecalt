# Parental consent verification for under-13 profiles

Status as of 2026-10-11. This is not legal advice; confirm with a lawyer before relying on it.

## Current state

- `ENABLE_MANAGED_CHILDREN=true` on Railway dev (`ecalt-api`) and production (`ecalt`).
- Under-13 profiles are created as `parental_consent_pending` and become active only after the parent completes card verification (`POST /api/v1/family/children/{child_uid}/verify/card`).
- Card verification is a Stripe Checkout session in `setup` mode: the card is saved, nothing is charged.
- `required_verification_tier()` in `app/core/jurisdiction.py` returns `card` for every under-13 and for every minor in India; `email_plus` otherwise.

## Is verification required?

Yes, for under-13s, though a card is not the only option.

- **US (COPPA):** the parent's consent must be verifiable before collecting a child's personal information (chats, progress, name). Email plus is not enough, because children's messages are sent to a third-party AI provider, which counts as disclosure.
- **FTC-accepted methods** include:
  - a payment card used in a monetary transaction (a purchase or a subscription)
  - a signed consent form
  - a phone or video call with trained staff
  - a government ID check
  - knowledge-based questions
- **The current card check may not qualify.** The FTC ties the card method to a monetary transaction; a $0 setup-mode session is weaker than a real charge.
- **India (DPDP):** verifiable parental consent applies to all children under 18.

Removing verification for under-13s while AI chat is enabled is not recommended.

## Paid subscription as verification (implemented)

A parent who already pays for ECALT has made a monetary transaction with a card or payment account, which fits the COPPA wording better than the $0 card check.

A subscription counts when it has `status = 'active'`, a plan other than `free_trial`, and a gateway reference (`stripe_subscription_id`, `razorpay_subscription_id` or `razorpay_last_payment_id`). Trials (`trialing`), coupon grants and admin-assigned plans don't count, because no payment was made.

Where it applies (`app/api/v1/endpoints/family.py`):

- **Creating a profile** (`POST /family/children`): a card-tier child of a paying parent is created `active` and `verified`. The response has `verification_required: false` and `verification_method: "paid_subscription"`.
- **Approving a teen's link request** (`POST /family/link-requests/{token}/approve`): a card-tier teen (India) is activated straight away.
- **Starting card verification** (`POST /family/children/{child_uid}/verify/card`) for a profile that is already pending: verifies without Stripe and returns `{"status": "verified", "checkout_url": "<FRONTEND_URL>/family"}`. The existing frontend redirects to that URL, so the dashboard reloads with the child active. No frontend change is needed.

Each verification writes a `consent_events` row with action `verified`, method `paid_subscription`, and the plan, gateway and subscription reference in `details`.

Parents on the free trial or without a plan still go through card verification.

Optional frontend follow-up: when `verify/card` returns `status: "verified"`, show a "Verified with your subscription" toast instead of redirecting.

## Open issue: `stripe_error` in production

Starting card verification in production returns:

```json
{"detail":{"error":"stripe_error","message":"Could not start verification. Please try again."}}
```

The real Stripe error is logged as `card verification session failed parent=... child=...`. To see it:

```
railway logs --service ecalt --environment production --lines 300 | grep -i "card verification session failed"
```

Likely causes to check in the Stripe dashboard:

1. The production `STRIPE_SECRET_KEY` is a live key (`sk_live_...`) from an account activated for live payments.
2. If the Stripe account is registered in India, Stripe limits saving cards without a charge, which is what setup mode does.

Dev (`ecalt-api`) uses a test key and showed no such error in its logs.

## Remaining before full rollout

- Fix the production Stripe error (still affects parents without a paid subscription).
- Test verification end to end in production with a real card (production uses live Stripe).
- Legal review of the updated consent copy, then bump `CONSENT_POLICY_VERSION`.
