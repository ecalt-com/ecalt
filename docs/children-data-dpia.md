# ECALT — Children's Data Protection Impact Assessment (DPIA)

**Version:** 1.0 · **Date:** 2026-07-10 · **Owner:** ECALT (developer.biswambar@gmail.com)
**Scope:** Processing of personal data of minors (under 18) on the ECALT learning
platform, including parent-managed accounts. Required under UK Children's Code /
GDPR Art. 35 for large-scale processing of children's data; also serves as the
COPPA written data-retention policy (2025 rule amendments).

---

## 1. Description of processing

ECALT is an AI-powered learning platform. Minors interact with AI-generated
learning journeys, step content, quizzes, and an AI chat/tutor. Accounts for
minors exist only with verifiable parental consent, via two paths:

- **Parent-created (managed):** an authenticated adult creates the child account
  from the Family dashboard, granting consent up front (Firebase email/password
  credential; Google OAuth is not used under 13).
- **Child-initiated (13+):** the teen signs up with Google and names a parent,
  whose consent is captured via a reviewed, explicit decision (never a bare link
  click — GET is read-only; consent requires a POST from a human action).

### Data collected from/about minors
| Category | Items | Basis |
|---|---|---|
| Identity | Name, login email, photo (Google sign-in, 13+ only), birth year+month | Account operation; age-gating |
| Learning activity | Questions asked, journeys, step progress, quiz answers, AI conversations, derived knowledge nodes / domain mastery | Core service |
| Consent records | Parent email, consent events (action, method, policy version, jurisdiction, hashed IP) | Legal obligation (proof of consent) |
| Technical | Token usage/cost accounting | Billing/abuse prevention |

**Not collected/done for minors:** advertising profiles, data sale, third-party
ad sharing, precise location, behavioral tracking for marketing (DPDP §9
compliance), raw IP in consent records (SHA-256 hash only).

## 2. Consent & verification (Art. 8 / COPPA VPC / DPDP)

- Jurisdiction matrix in `backend/app/core/jurisdiction.py` (GDPR member-state
  derogations; US 13; India 18; defaults conservative at 16).
- Product policy is stricter than most local law: **all** minors require parental
  consent; under-13 self-signup is impossible (rejected pre-storage, and the
  Firebase auth record created by Google sign-in is purged).
- Verification tiers: `email_plus` (explicit reviewed approval + 24h follow-up
  notice with objection link) for 13+ outside India; `card` (Stripe SetupIntent
  micro-verification, nothing charged, no payment method retained) for all
  under-13s and all minors in India; `id` tier reserved for third-party providers.
- Consent audit log (`consent_events`) is append-only (DB trigger), survives
  account deletion via uid pseudonymization, and is exportable by the parent.
- Consent is as easy to withdraw as to give: self-serve revocation from the
  dashboard → immediate pause, 14-day grace, hard deletion.

## 3. Parental controls & transparency

Parents see topics, progress, quiz scores, and conversation *titles*; full
transcripts only for managed under-13s (COPPA review right) or by explicit family
setting. **The child is shown exactly what the parent can see** (`/family/my-family`
disclosure — Children's Code transparency duty). Controls: pause, AI-chat off
(default off under 13), content age band (overrides client), digest opt-out,
export, delete.

## 4. Retention policy (written policy per COPPA 2025 amendments)

| Data | Retention | Enforcement |
|---|---|---|
| Pending accounts whose consent never arrived | 30 days, then hard delete (incl. Firebase credential) | daily lifecycle job |
| Inactive linked child accounts | 12 months inactivity → parent notice; +30 days → 14-day grace deletion (parent can cancel) | daily lifecycle job |
| Deleted accounts | immediate cascade; consent events retained pseudonymized (legal defense); deletion logged in `deletion_requests` | on request |
| Consent proof | retained pseudonymized indefinitely (legitimate interest / legal obligation) | append-only table |
| Policy re-consent lapse | children paused 30 days after un-actioned re-consent notice | daily lifecycle job |
| Age-up | at 18: family link graduated, controls removed, child re-consents as adult | daily lifecycle job |

## 5. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Child fakes parent email (self-approval) | High | Authenticated-adult approval path; self-approval blocked; email-plus delayed objection notice; card tier where law demands more |
| Email prefetcher "confirms" consent | High | GET is read-only; consent only via explicit POST |
| AI chat exposure for young children | High | Chat default **off** for under-13 managed accounts; model-level guardrails; content filter; parent toggle |
| Consent proof lost | Med | Append-only audit table, survives deletion pseudonymized |
| Under-13 PII lingering in Firebase after age-gate rejection | Med | Automatic Firebase auth deletion on rejection (requires `FIREBASE_SERVICE_ACCOUNT_JSON`) |
| Over-collection | Med | Birth month+year only (no full DOB); hashed IPs; no ads/tracking; minimal child profile |
| Orphaned children on parent deletion | Med | Deletion blocked while managed under-13s exist; teens unlinked + notified |
| Wrong-jurisdiction consent age | Med | Country matrix + conservative default (16); jurisdiction recorded at consent time |
| Stale consent after policy change | Low | Version-stamped consent; automated re-consent notices; pause on lapse |

## 6. Residual risk & sign-off

Residual risks accepted for launch: email-plus remains spoofable by a teen with
access to a parent's inbox (industry-standard residual risk; mitigated by the
follow-up notice); Stripe card verification excludes card-less parents in India
(DigiLocker-class provider planned — under-13/India rollout stays behind
`ENABLE_MANAGED_CHILDREN` until then).

Review cadence: re-assess on every `CONSENT_POLICY_VERSION` bump, new jurisdiction
launch, or new child-facing feature (especially anything social or generative).
