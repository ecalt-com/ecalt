# graphify
- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.

---

# ECALT Backend — Developer Reference

FastAPI service that powers ECALT (AI-generated learning journeys, chat, quizzes, payments, parental accounts, notifications). Deployed on Railway (Docker). Data lives in Supabase Postgres, accessed with **raw SQL through psycopg2** (no ORM, no supabase-py client). Auth is Firebase ID tokens. The SPA in `../frontend` calls it via same-origin `/api/*` rewrites.

---

## Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI + uvicorn, Python 3.11 (Dockerfile) |
| Config | pydantic-settings (`app/core/config.py`, reads `.env`) |
| DB | Supabase Postgres via `psycopg2` `ThreadedConnectionPool`, `RealDictCursor` |
| Auth | Firebase ID token (JWT verified with PyJWT against Google certs) |
| AI | OpenAI + Anthropic via `provider_service` (per-interaction provider/model, admin-switchable) |
| Payments | Stripe (global) + Razorpay (India) |
| Notifications | Brevo (email, HTTP API preferred; SMTP fallback), Twilio WhatsApp |
| Jobs | APScheduler (in-process, only when `SCHEDULER_ENABLED=true`) |
| Rate limiting | slowapi (`app/core/limiter.py`, keyed by remote IP) |
| Observability | Sentry, structured logging (`logging_config.py`), `X-Request-Id` header |

---

## Commands

```bash
cd backend
source .venv/bin/activate              # (a legacy venv/ also exists — prefer .venv)
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000   # docs at http://localhost:8000/docs

pytest                                  # unit/api/services tests; integration excluded by default
pytest -m integration                   # needs a live DB
pytest tests/unit/test_budget.py -k name

python scripts/run_migrations.py --dry-run   # list pending SQL migrations
python scripts/run_migrations.py             # apply pending (tracked in schema_migrations)
python scripts/make_admin.py --email you@x.com [--revoke]   # or --uid <firebase_uid>
```

> **⚠️ Local dev talks to the PRODUCTION database and Brevo.** Keep `SCHEDULER_ENABLED=false` locally (the code default is `true`!) — a second scheduler double-sends emails with localhost links. Treat any local write as a prod write.

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
│   │   ├── auth.py             # Auth dependencies (see below)
│   │   ├── jurisdiction.py     # Digital-consent age by country, age/consent/verification-tier rules
│   │   ├── impersonation_audit.py  # Middleware that audits admin impersonated requests
│   │   ├── limiter.py, logging_config.py
│   │   └── supabase.py         # Legacy/unused supabase-py client — don't build on it
│   ├── models/                 # Pydantic schemas: schemas.py, visual_schemas.py, visual_recipe_schemas.py
│   └── services/               # Business logic (one module per domain — see below)
├── tests/                      # unit/, api/, services/, integration/ + conftest.py (plan fixtures, mock DB)
├── scripts/                    # migrations runner, make_admin, eval/backfill/test-send scripts
├── plans/                      # Feature plans + frontend-change docs (parental-accounts, visual-intelligence, …)
├── Dockerfile, railway.json, pytest.ini, requirements.txt
```

**SQL migrations live at the repo root: `../migrations/NNN_name.sql`** (not `backend/migrations/` — `run_migrations.py` still points at `backend/migrations`, so check/fix its `MIGRATIONS_DIR` before running). Reference schema dumps are in `../supbase/schema.sql` / `data.sql`. Number new migrations sequentially and make them idempotent (`IF NOT EXISTS`).

---

## Request Pipeline

`main.py` registers, in order of effect:
1. `request_middleware` — assigns `request_id`, logs method/path/status/duration, sets `X-Request-Id`.
2. `ImpersonationAuditMiddleware` — records actions performed under an admin impersonation session.
3. `CORSMiddleware` — origins from `ALLOWED_ORIGINS` (comma-separated, `settings.allowed_origins`).
4. Exception handlers: every `HTTPException` is logged (5xx with traceback); unhandled exceptions → JSON 500 (keeps CORS headers).

`redirect_slashes=False` — define list routes as `@router.get("")`, not `"/"`.

Lifespan: fails startup in non-development if `NOTIFICATION_SIGNING_SECRET` is unset, logs the email transport, warms the DB pool, and starts APScheduler if enabled.

---

## Auth Dependencies (`app/core/auth.py`)

| Dependency | Returns | Use for |
|---|---|---|
| `get_optional_user` | `uid \| None` | Public endpoints that personalise when signed in |
| `get_required_user` | `uid` (401 otherwise) | Signed-in, **status not checked** (e.g. `/users` bootstrap, consent flow) |
| `get_active_user` | `uid` | **Default for learner features.** 403 `{error: consent_pending}` / `{error: account_paused}`; status cached 60 s, fails closed (503) |
| `get_admin_user` | `uid` | Admin endpoints (403 otherwise) |
| `get_acting_uid` | `(acting_uid, real_uid)` | Endpoints admins may impersonate (`X-Impersonate-Session` header) |
| `get_optional_acting_uid` | `uid \| None` | Optional-auth + impersonation |
| `ensure_chat_allowed(uid)` | — | Raise 403 when parent disabled AI chat |
| `verify_parent_of(parent, child)` | — | Guard every `/family/children/{child_uid}/…` route |
| `invalidate_status_cache(uid)` | — | Call after changing `account_status` / `paused` |

Structured errors use `detail={"error": "<code>", "message": "..."}` — the frontend reads `detail.error` via `apiErrorCode()`.

---

## Database Access

```python
from app.core.database import get_db

with get_db() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT ... WHERE uid = %s", (uid,))
        row = cur.fetchone()          # dict (RealDictCursor)
```

- Auto-commits on success, rolls back on exception. Non-HTTP exceptions are converted to `HTTPException(500)`; `HTTPException`s raised inside pass through after rollback.
- Stale connections are detected and replaced. Always use parameterised `%s` placeholders — never f-string SQL values.
- Sync psycopg2 inside async endpoints is the existing pattern; keep DB blocks short.

---

## AI Providers & Prompts (`services/provider_service.py`)

- Each **interaction type** (`daily_chat`, `spark`, `journey`, `step_content`, `content_critic`, `quiz`, `journey_tutor`, `knowledge_extraction`, `mind_signature`, `visual_*`, `journey_image`, …) maps to a provider + model + optional `style_prompt`, stored in the **`ai_provider_config`** table and editable from the admin panel.
- `DEFAULT_CONFIG` / `_*_STYLE_DEFAULT` constants in code are **fallbacks only**, used when the DB row (or `style_prompt`) is NULL. **Editing a prompt in code does not change prod if the DB row has a value** — update the DB (admin Prompts tab or SQL) too. Prompt history is kept (`get_prompt_history`).
- Call models through `complete_text(...)` / `stream_completion(...)`; never instantiate SDK clients in endpoints.
- Cost tracking: `cost_for_tokens` / `cost_for_images` using `COST_PER_TOKEN`. Add new models there or they'll be costed wrong.

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
- Budgets are in **cents** per plan (`token_budget_cents`); free trial also has `lifetime_message_limit`. Family plans share spend across members (`get_family_member_uids`). Coupon extras add credits/messages.
- Plan fixtures for tests are in `tests/conftest.py` (`FREE_TRIAL`, `INDIVIDUAL`, `STUDENT`, `FAMILY`).

---

## Services (high level)

| Area | Modules |
|---|---|
| Journeys & content | `ai_service` (journey + step content generation, critic), `spark_service`, `suggestion_service`, `image_service` (journey hero images → Supabase Storage) |
| Learning loop | `chat_service` (SSE chat), `quiz_service` (quiz sets, hints, grading, anchors), `mastery_service`, `knowledge_service`, `fingerprint_service`, `interest_profile_service`, `mind_signature_service` |
| Visual intelligence | `visual_orchestrator/planner/router/recipe/registry/retrieval/image/video/telemetry_service`, `wikimedia_retrieval_adapter` — all gated by `VISUAL_*` flags |
| Money | `subscription_service`, `stripe_service`, `razorpay_service`, `coupon_service` |
| Accounts & compliance | `account_service` (deletion, export), `consent_service` (parental consent, policy version), `firebase_admin` (managed child accounts), `content_filter` |
| Notifications | `notification_service` (queue, prefs, caps, signed unsubscribe), `email_service` (Brevo), `whatsapp_service` (Twilio), `copy_generator`, `scheduler` |
| Config | `provider_service` (AI config, prompts, notification templates, costs) |

---

## Scheduler (`services/scheduler.py`)

Runs only when `SCHEDULER_ENABLED=true` — **exactly one instance (prod)**. Jobs: notification `queue_processor` & `daily_spark_dispatch` (every 15 min), re-engagement ladder, streak lost/risk/milestone checks, mind-signature nudge, journey-completion nudge, weekly learner digest, consent follow-ups, weekly family digest, scheduled account deletions (03:30), family lifecycle (04:00), marketplace popularity scan (every 6 h). Jobs must catch their own exceptions and log.

---

## Feature Flags & Key Settings (`config.py`)

| Setting | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | Non-dev enforces `NOTIFICATION_SIGNING_SECRET` |
| `SCHEDULER_ENABLED` | `True` | Set `false` everywhere except prod |
| `NOTIFICATIONS_EMAIL_ENABLED` / `_WHATSAPP_ENABLED` | `True` | Global kill-switches |
| `ENABLE_MANAGED_CHILDREN` | `False` | Parent-created child accounts (needs `FIREBASE_SERVICE_ACCOUNT_JSON`) |
| `MAX_CHILDREN_PER_PARENT` | `5` | |
| `VISUAL_INTELLIGENCE_ENABLED`, `VISUAL_NATIVE_RENDER_ENABLED`, `VISUAL_RETRIEVAL_ENABLED`, `VISUAL_IMAGE_GENERATION_ENABLED`, `VISUAL_VIDEO_GENERATION_ENABLED`, `VISUAL_TELEMETRY_ENABLED` | `False` | Visual learning objects |
| `GEO_DEFAULT_COUNTRY` | `IN` | Fallback for `/geo/country` (drives Razorpay vs Stripe) |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | empty | Required for image storage; endpoints return 503 without them |

Other env vars (see `.env.example`): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `FIREBASE_PROJECT_ID`, `DATABASE_URL` (or `DB_*`), `ALLOWED_ORIGINS`, `FRONTEND_URL` (used in email links), Stripe/Razorpay keys + webhook secrets, Brevo/SMTP, Twilio, `NOTIFICATION_SIGNING_SECRET`, `SENTRY_DSN`, `LOG_LEVEL`.

---

## Payments

- `/subscriptions/config` exposes public keys (Stripe publishable, Razorpay key id) to the frontend.
- Stripe: checkout session → webhook (`STRIPE_WEBHOOK_SECRET`) → `upsert_subscription_from_stripe`.
- Razorpay: subscription or one-off order → client checkout → server-side signature verification + webhook (`RAZORPAY_WEBHOOK_SECRET`). Plans carry `base_price_inr_paise` for INR pricing.
- Keep Stripe/Razorpay behaviour in parity — `tests/unit/test_payment_gateway_parity.py` enforces it.

---

## Parental Accounts & Compliance

- `jurisdiction.py` decides the digital-consent age per country, hard block (under 13), and verification tier.
- `POST /users` is the sign-in bootstrap: returns `needs_birth_year`, `account_status` (`active` | `parental_consent_pending`), `role` (`learner` | `parent`), `onboarding_done`.
- Consent emails carry signed tokens → `/consent/confirm` on the frontend. Revocation pauses immediately and deletes after 14 days (scheduler).
- Policy-version bumps trigger re-consent (`ReconsentBanner` on the frontend).
- Plan docs: `plans/parental-accounts/` (incl. `launch-checklist.md`).

---

## Conventions

- New router: create `endpoints/<name>.py` with `router = APIRouter()`, then register it in `api/v1/router.py` with a prefix + tag.
- Put logic in `services/`, keep endpoints thin (validate → auth/budget → service → record usage → respond).
- Request/response models: Pydantic v2 (inline in the endpoint or in `models/schemas.py`).
- Use `logging.getLogger(__name__)`; never log tokens, emails bodies, or PII payloads.
- Rate-limit public/AI endpoints with `@limiter.limit(...)` (needs a `request: Request` param).
- Add tests under `tests/unit` (pure logic, mock `get_db`) or `tests/api`; mark DB-dependent tests `@pytest.mark.integration`.
- When a backend feature needs frontend work, write the frontend changes up as an md doc in `plans/<feature>/` rather than implementing them directly.

## Deployment

- Railway builds the `Dockerfile` (`uvicorn app.main:app --port ${PORT:-8000}`), restart on failure.
- Prod: `ecalt-production.up.railway.app` (from `master`). Dev: `ecalt-api-dev.up.railway.app` (from `feature/dev`).
- Schema changes are **not** applied on deploy — run the migration against the DB (script or Supabase MCP) before/with the release.
