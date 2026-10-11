# ECALT Backend — Developer Reference

FastAPI service behind ECALT: AI-generated learning journeys, chat, quizzes, payments, parental/family accounts and notifications. Deployed on Railway (Docker). Data lives in Supabase Postgres, accessed with **raw SQL through psycopg2** (no ORM, no supabase-py client). Auth is Firebase ID tokens. The SPA in `../frontend` calls it via same-origin `/api/*` rewrites.

> **⚠️ Local dev talks to the PRODUCTION database and Brevo.** Treat every local write as a prod write. Keep `SCHEDULER_ENABLED=false` locally (the code default is `true`!) — a second scheduler double-sends emails with localhost links.

---

## Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI + uvicorn, Python 3.11 (Dockerfile) |
| Config | pydantic-settings (`app/core/config.py`, reads `.env`) |
| DB | Supabase Postgres via `psycopg2` `ThreadedConnectionPool`, `RealDictCursor` |
| Auth | Firebase ID token (JWT verified with PyJWT against Google certs) |
| AI | OpenAI + Anthropic via `provider_service` (provider/model per interaction type, admin-switchable) |
| Payments | Stripe (global) + Razorpay (India) |
| Notifications | Brevo email (HTTP API preferred, SMTP fallback), Twilio WhatsApp |
| Jobs | APScheduler, in-process, only when `SCHEDULER_ENABLED=true` |
| Rate limiting | slowapi (`app/core/limiter.py`, keyed by remote IP) |
| Observability | Sentry, structured logging (`logging_config.py`), `X-Request-Id` header |

---

## Commands

```bash
cd backend
source .venv/bin/activate                   # a legacy venv/ also exists — use .venv
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000   # OpenAPI docs at http://localhost:8000/docs

pytest                                      # unit/api/services; integration excluded (pytest.ini addopts)
pytest -m integration                       # needs a live DB
pytest tests/unit/test_budget.py -k name    # single file / test

python scripts/run_migrations.py --dry-run  # list pending SQL migrations
python scripts/run_migrations.py            # apply pending (tracked in schema_migrations)
python scripts/make_admin.py --email you@x.com [--revoke]   # or --uid <firebase_uid>
```

**Verify every change with `pytest`** before calling it done.

- Run tests with a dead DB URL so nothing can reach production: `DATABASE_URL=postgresql://x:y@127.0.0.1:1/none pytest`. Repeated failed logins also trip the Supabase pooler's auth circuit breaker.
- Settings are read from `.env`, so a test that depends on a flag (e.g. `ENABLE_MANAGED_CHILDREN`) must patch it explicitly — never rely on the local `.env` value.
- 62 tests fail on `feature/dev` before any change (as of 2026-10-11). Compare the failure count before and after your change rather than expecting a clean run.

---

## Layout

```
backend/
├── app/
│   ├── main.py                 # App factory: lifespan (pool warm-up, scheduler), CORS, middleware, error handlers
│   ├── api/v1/
│   │   ├── router.py           # Mounts every endpoint module under /api/v1/<prefix>
│   │   └── endpoints/          # admin, chat, coupons, explore, family, geo, health, journeys, knowledge,
│   │                           # mind_signature, notifications, passport, progress, quiz, session,
│   │                           # sitemap, spark, subscriptions, users
│   ├── core/
│   │   ├── config.py           # Settings (env vars + feature flags)
│   │   ├── database.py         # get_db() context manager over the pool
│   │   ├── auth.py             # Auth / profile / impersonation dependencies (see below)
│   │   ├── jurisdiction.py     # Digital-consent age by country, age/consent/verification-tier rules
│   │   ├── impersonation_audit.py  # Middleware that audits admin-impersonated requests
│   │   ├── limiter.py, logging_config.py
│   │   └── supabase.py         # Legacy/unused supabase-py client — don't build on it
│   ├── models/                 # Pydantic schemas: schemas.py, visual_schemas.py, visual_recipe_schemas.py
│   └── services/               # Business logic, one module per domain (see Services)
├── tests/                      # unit/, api/, services/, integration/ + conftest.py (plan fixtures, mock DB)
├── scripts/                    # migration runner, make_admin, eval/backfill/test-send scripts
├── plans/                      # Feature plans + frontend-change docs (see Plans)
└── Dockerfile, railway.json, pytest.ini, requirements.txt
```

### Migrations
- SQL migrations live at the **repo root: `../migrations/NNN_name.sql`** (currently `001`–`013`).
- ⚠️ `scripts/run_migrations.py` sets `MIGRATIONS_DIR = backend/migrations`, which doesn't exist — point it at `../migrations` (or apply via the Supabase MCP / SQL editor) before running.
- Number new files sequentially and make them idempotent (`IF NOT EXISTS`, guarded `DO $$` blocks). Prefer additive migrations that are safe to apply before the code deploys.
- Schema changes are **not** applied on deploy — run them against the DB before/with the release.
- Reference schema dumps: `../supbase/schema.sql` / `data.sql`.

---

## Request Pipeline (`main.py`)

1. `request_middleware` — assigns `request_id`, logs method/path/status/duration, sets `X-Request-Id`.
2. `ImpersonationAuditMiddleware` — records actions performed under an admin impersonation session.
3. `CORSMiddleware` — origins from `ALLOWED_ORIGINS` (comma-separated → `settings.allowed_origins`).
4. Exception handlers — every `HTTPException` is logged (5xx with traceback); unhandled exceptions → JSON 500 that keeps CORS headers.

- `redirect_slashes=False` — define collection routes as `@router.get("")`, **not** `"/"`.
- Lifespan: refuses to start outside `development` if `NOTIFICATION_SIGNING_SECRET` is unset; logs the email transport; warms the DB pool; starts APScheduler if enabled.

---

## Auth (`app/core/auth.py`)

### Identity resolution
1. Bearer Firebase ID token → Firebase uid.
2. `_map_identity` maps it to `users.uid` via `auth_identities` (identical except for a *claimed* family profile, whose data stays under its `prof_…` uid). Cached 60 s, fails closed (503).
3. If the request carries `X-Profile-Id` naming one of the account's family profiles, the **acting uid becomes that profile** (verified via an active `family_links` row + `users.profile_type='profile'`, cached 60 s). Otherwise it's the signed-in account. `X-Profile-Id` + `X-Impersonate-Session` together → 400.

### Dependencies

| Dependency | Returns | Use for |
|---|---|---|
| `get_signed_in_uid` | `uid \| None` | The signed-in **account**, never a profile — `POST /users` bootstrap, profile picker |
| `get_optional_user` | `uid \| None` | Public endpoints that personalise when signed in (profile-aware) |
| `get_required_user` | `uid` (401 otherwise) | Signed in, **status not checked** (bootstrap, consent flow) |
| `get_active_user` | `uid` | **Default for learner features.** 403 `consent_pending` / `account_paused`; status cached 60 s, fails closed (503) |
| `get_account_holder` | `uid` | Account-level actions; 403 `parent_profile_required` when called from inside a child profile |
| `get_active_account_holder` | `uid` | Account holder + active status, no PIN (profile picker, setting the PIN) |
| `get_active_signed_in_account` | `uid` | Signed-in, active account, **ignoring `X-Profile-Id`**. Only for `POST /family/pin/verify` and `/pin/reset` — they are how a parent leaves a child profile, so the request still carries the profile header. Don't use it elsewhere |
| `get_unlocked_account_holder` | `uid` | Account holder + parent PIN unlock, no status check (e.g. account deletion) |
| `get_parent_session` | `uid` | Active account holder + parent PIN unlock. **Default for `/family` routes** |
| `get_admin_user` | `uid` | Admin endpoints (403 otherwise) |
| `get_acting_uid` / `get_active_acting_uid` | `(acting_uid, real_uid)` | Endpoints admins may impersonate (`X-Impersonate-Session`) |
| `get_optional_acting_uid` | `uid \| None` | Optional auth + impersonation |

Helpers: `ensure_chat_allowed(uid)` (403 when a parent disabled AI chat), `verify_parent_of(parent, child)` (guard every `/family/children/{child_uid}/…` route), `require_parent_unlock(uid, token)`.

**Cache invalidation — call these or users see stale state for up to 60 s:**
- `invalidate_status_cache(uid)` after changing `account_status` / `paused`.
- `invalidate_profile_cache(parent_uid=…, profile_uid=…)` after creating, deleting, revoking or claiming a profile.
- `invalidate_identity_cache(firebase_uid)` after writing `auth_identities`.

**Structured errors** use `detail={"error": "<code>", "message": "..."}` — the frontend reads `detail.error` via `apiErrorCode()`. Known codes: `consent_pending`, `account_paused`, `profile_not_allowed`, `parent_profile_required`, `parent_unlock_required`, `conflicting_headers`, `under_13_not_available`.

---

## Database Access

```python
from app.core.database import get_db

with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT ... WHERE uid = %s", (uid,))
        row = cur.fetchone()          # dict (RealDictCursor)
```

- Auto-commits on success, rolls back on exception. Non-HTTP exceptions become `HTTPException(500)`; `HTTPException`s raised inside pass through after rollback.
- Stale connections are detected and replaced.
- **Always use `%s` placeholders — never f-string SQL values.**
- Sync psycopg2 inside async endpoints is the established pattern; keep DB blocks short.
- All learner data (~31 `uid`/`user_id` columns) is keyed by `users.uid` (text PK). A family profile is just another `users` row, so per-uid queries work for profiles unchanged.

---

## AI Providers & Prompts (`services/provider_service.py`)

- Each **interaction type** (`daily_chat`, `spark`, `journey`, `step_content`, `content_critic`, `quiz`, `journey_tutor`, `knowledge_extraction`, `mind_signature`, `visual_*`, `journey_image`, …) maps to provider + model + optional `style_prompt` in the **`ai_provider_config`** table, editable from the admin panel.
- `DEFAULT_CONFIG` / `_*_STYLE_DEFAULT` constants in code are **fallbacks only**, used when the DB row (or its `style_prompt`) is NULL. **Editing a prompt in code does not change prod if the DB row has a value** — update the DB too (admin Prompts tab or SQL). Prompt history is kept (`get_prompt_history`).
- Call models only through `complete_text(...)` / `stream_completion(...)`; never instantiate SDK clients in endpoints.
- Cost tracking: `cost_for_tokens` / `cost_for_images` using `COST_PER_TOKEN`. **Add new models there** or usage is costed wrong.

---

## Budgets & Usage (`services/subscription_service.py`)

Every AI-backed endpoint follows:

```python
allowed, reason = check_budget(uid)
if not allowed:
    raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})
... call model ...
record_usage(uid, ..., input_tokens, output_tokens, ...)   # or record_image_usage
```

- Budgets are in **cents** per plan (`token_budget_cents`); the free trial also has `lifetime_message_limit`. Coupon extras add credits/messages.
- Family plans share spend across members (`get_family_member_uids`), which includes family profiles.
- Test plan fixtures: `tests/conftest.py` (`FREE_TRIAL`, `INDIVIDUAL`, `STUDENT`, `FAMILY`).

---

## Services

| Area | Modules |
|---|---|
| Journeys & content | `ai_service` (journey + step content generation, critic), `spark_service`, `suggestion_service`, `image_service` (journey hero images → Supabase Storage) |
| Learning loop | `chat_service` (SSE chat), `quiz_service` (quiz sets, hints, grading, anchors), `mastery_service`, `knowledge_service`, `fingerprint_service`, `interest_profile_service`, `mind_signature_service` |
| Visual intelligence | `visual_orchestrator/planner/router/recipe/registry/retrieval/image/video/telemetry_service`, `wikimedia_retrieval_adapter` — all gated by `VISUAL_*` flags |
| Money | `subscription_service`, `stripe_service`, `razorpay_service`, `coupon_service` |
| Accounts & compliance | `account_service` (deletion, export), `consent_service` (parental consent, policy version), `profile_service` (parent PIN, unlock tokens), `firebase_admin` (delete/purge Firebase logins), `content_filter` |
| Notifications | `notification_service` (queue, prefs, caps, signed unsubscribe), `email_service` (Brevo), `whatsapp_service` (Twilio), `copy_generator`, `scheduler` |
| Config | `provider_service` (AI config, prompts, notification templates, costs) |

---

## Parental Accounts, Family Profiles & Compliance

### Age & consent
- `jurisdiction.py` decides the digital-consent age per country, the hard floor (`HARD_FLOOR_AGE = 13` for self sign-up) and the verification tier.
- `POST /users` is the sign-in bootstrap: returns `needs_birth_year`, `account_status` (`active` | `parental_consent_pending`), `role` (`learner` | `parent`), `onboarding_done`.
- Teens (13–17) can self sign-up with Google → parent email → signed consent token → frontend `/consent/confirm` → `family_links` row. Parents can also approve via `/family/link-requests/{token}/approve`.
- Revoking consent pauses immediately and deletes after 14 days (scheduler). Policy-version bumps trigger re-consent.
- Plan docs: `plans/parental-accounts/` (incl. `launch-checklist.md`).

### Family profiles (`plans/family-profiles/`)
Children (all under-13s, optionally teens) use ECALT as **profiles on the parent's Google login** — no child email or password.
- A profile is a `users` row with `profile_type='profile'`, uid `prof_<hex>`, `email` NULL, linked via `family_links`; `child_settings.managed = true`. Accounts with a Firebase login have `profile_type='account'`.
- Parent acts as a profile by sending `X-Profile-Id` (see Auth).
- **Parent PIN** (`parent_pins`, scrypt-hashed, 5 attempts → 15 min lock): `POST /family/pin/verify` mints a 15-min HMAC unlock token sent as `X-Parent-Unlock` on parent-only requests. Required only when the account has at least one profile. Forgot-PIN → `/family/pin/reset` after a fresh Google sign-in.
- Lifecycle: a profile can be **claimed** by the child's own Google login (`POST /users/claim`, `/family/children/{uid}/claim-invite`) → `auth_identities` maps the new Firebase uid to the existing `prof_…` uid. The scheduler ages up unclaimed profiles and handles turning 13.
- **Under-13s never get a login or password** — only a profile under the parent's login. The claim flow refuses under-13s (`too_young_to_claim`).
- Under-13 profile creation is gated by `ENABLE_MANAGED_CHILDREN` (403 `under_13_not_available` when off). It is **on** in Railway dev and production since 2026-10-11.
- **PIN endpoints from inside a child profile:** `/family/pin/verify` and `/family/pin/reset` use `get_active_signed_in_account` so they work while `X-Profile-Id` is set (otherwise the parent is locked in). Every other parent-only route still rejects the profile header.
- Migration: `../migrations/013_family_profiles.sql`. The frontend side is implemented (`/profiles`, `/claim`, PIN prompt; `/kids-login` now redirects to `/`).

### Parental verification (`plans/family-profiles/parental-consent-verification.md`)
`required_verification_tier()` returns `card` for every under-13 and for every minor in India, `email_plus` otherwise. A card-tier child stays `parental_consent_pending` until verified, by either:
- **Paid subscription** (`_paid_subscription` / `_verify_via_subscription` in `endpoints/family.py`): the parent has a subscription with `status = 'active'`, a plan other than `free_trial`, and a Stripe or Razorpay reference. Trials, coupon grants and admin-assigned plans don't count. Applied on profile creation, on teen link approval, and in `POST /family/children/{uid}/verify/card` (which then returns `checkout_url` = `<FRONTEND_URL>/family` instead of a Stripe URL).
- **Card check:** Stripe Checkout in `setup` mode (nothing charged), confirmed by `/verify/card/confirm`.

Both write a `consent_events` row with action `verified` and method `paid_subscription` or `card`.

### Parental controls
Built on `family_links` + `child_settings`, per uid: dashboard (overview/activity/transcripts), pause, chat on/off, age band, transcript visibility, digest, verification (paid subscription or Stripe setup-mode card check), consent audit log (`consent_events`), re-consent, revocation with 14-day grace, export, delete.

---

## Payments

- `GET /subscriptions/config` exposes public keys (Stripe publishable, Razorpay key id) to the frontend.
- **Stripe:** checkout session → webhook (`STRIPE_WEBHOOK_SECRET`) → `upsert_subscription_from_stripe`.
- **Razorpay:** subscription or one-off order → client checkout → server-side signature verification + webhook (`RAZORPAY_WEBHOOK_SECRET`). Plans carry `base_price_inr_paise` for INR pricing.
- Keep Stripe and Razorpay behaviour in parity — `tests/unit/test_payment_gateway_parity.py` enforces it.

---

## Scheduler (`services/scheduler.py`)

Runs only when `SCHEDULER_ENABLED=true` — **exactly one instance (prod)**. Jobs:
- Notifications: `queue_processor` and `daily_spark_dispatch` (every 15 min), re-engagement ladder, streak lost/risk/milestone, mind-signature nudge, journey-completion nudge, weekly learner digest.
- Family/compliance: consent follow-ups, weekly family digest, scheduled account deletions (03:30), family lifecycle (04:00 — age-up, turning 13, expiry, retention).
- Marketplace popularity scan (every 6 h).

Jobs must catch and log their own exceptions.

---

## Settings & Feature Flags (`config.py`)

| Setting | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | Non-dev enforces `NOTIFICATION_SIGNING_SECRET` |
| `SCHEDULER_ENABLED` | `True` | **Set `false` everywhere except prod** |
| `NOTIFICATIONS_EMAIL_ENABLED` / `NOTIFICATIONS_WHATSAPP_ENABLED` | `True` | Global kill-switches |
| `ENABLE_MANAGED_CHILDREN` | `False` | Under-13 family profiles; 13+ profiles can be created regardless. Set `true` on Railway dev + production |
| `MAX_CHILDREN_PER_PARENT` | `5` | |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | empty | Firebase Admin REST — purging under-13 / deleted-account logins |
| `VISUAL_INTELLIGENCE_ENABLED`, `VISUAL_NATIVE_RENDER_ENABLED`, `VISUAL_RETRIEVAL_ENABLED`, `VISUAL_IMAGE_GENERATION_ENABLED`, `VISUAL_VIDEO_GENERATION_ENABLED`, `VISUAL_TELEMETRY_ENABLED` | `False` | Visual learning objects; disabled → API returns no visual |
| `GEO_DEFAULT_COUNTRY` | `IN` | Fallback for `/geo/country` (drives Razorpay vs Stripe) |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | empty | Required for image storage; endpoints return 503 without them |

Other env vars (see `.env.example`): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `FIREBASE_PROJECT_ID`, `DATABASE_URL` (or `DB_*`), `ALLOWED_ORIGINS`, `FRONTEND_URL` (used in email links), Stripe/Razorpay keys + webhook secrets, Brevo/SMTP, Twilio, `NOTIFICATION_SIGNING_SECRET`, `SENTRY_DSN`, `LOG_LEVEL`.

---

## Conventions

- **New router:** create `endpoints/<name>.py` with `router = APIRouter()`, register it in `api/v1/router.py` with a prefix + tag.
- **Thin endpoints:** validate → auth/budget → service → record usage → respond. Business logic lives in `services/`.
- **Pick the right auth dependency** (table above). Learner features → `get_active_user` (or `get_active_acting_uid` if admins may impersonate). Family/parent-only → `get_parent_session`.
- **Models:** Pydantic v2, inline in the endpoint or in `models/schemas.py`.
- **Logging:** `logging.getLogger(__name__)`; never log tokens, PINs, email bodies or PII payloads.
- **Rate limiting:** public/AI endpoints get `@limiter.limit(...)` (needs a `request: Request` param).
- **Tests:** `tests/unit` (pure logic, mock `get_db`) or `tests/api`; mark DB-dependent tests `@pytest.mark.integration`.
- **Null emails:** profile rows have `email IS NULL` — guard any code that emails or displays a user's address.
- **Frontend work:** when a backend feature needs frontend changes, write them up as an md doc in `plans/<feature>/` instead of implementing them directly.

---

## Plans (`plans/`)

| Folder | Topic |
|---|---|
| `parental-accounts/` | Consent, family links, controls, launch checklist |
| `family-profiles/` | Kid profiles under the parent login + PIN (replaces `/kids-login`); `parental-consent-verification.md` covers the verification rules |
| `journey-images/` | Journey hero images in Supabase Storage |
| `course-content-quality/` | Content-quality improvements for generated courses |
| `visual-intelligence/` | Visual learning objects pipeline |

---

## Deployment

- Railway builds the `Dockerfile` (`uvicorn app.main:app --port ${PORT:-8000}`), restart on failure.
- **Prod:** `ecalt-production.up.railway.app` (from `master`). **Dev:** `ecalt-api-dev.up.railway.app` (from `feature/dev`).
- Run migrations against the DB before/with the release — deploys don't apply them.
- DB-stored config (AI prompts, provider/model choices, notification templates) changes need a DB write, not just a code deploy.
