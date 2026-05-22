# Notification System — Implementation Plan

> Scope: Email + WhatsApp only (Push/SMS deferred).  
> Backend: FastAPI + PostgreSQL (Supabase). Email via SendGrid. WhatsApp via Twilio.

---

## Phases Overview

| Phase | What gets built | Deliverable |
|---|---|---|
| 1 | DB schema + config + base service skeleton | Foundation |
| 2 | Email channel (SendGrid) + 2 notification types | Daily Spark + Re-engagement emails |
| 3 | WhatsApp channel (Twilio) + opt-in flow | Daily Spark + Cliffhanger WhatsApp |
| 4 | Anti-annoyance engine + engagement tracking | Daily cap, quiet hours, quiet mode |
| 5 | Notification preference API endpoints | User can manage channels + quiet hours |
| 6 | Scheduled triggers (APScheduler) | Cron jobs fire notifications automatically |
| 7 | Remaining notification types | Connection Alert, World Event Hook, Milestone, Mind Signature, Family Highlight |

---

## Phase 1 — Foundation (DB + Config + Base Service)

### 1.1 New environment variables (`config.py`)

```
SENDGRID_API_KEY
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_FROM       # e.g. whatsapp:+14155238886
```

### 1.2 DB migrations (new tables)

**`notification_preferences`** — one row per user
```sql
uid                     TEXT PRIMARY KEY REFERENCES users(uid)
email_enabled           BOOLEAN DEFAULT TRUE
whatsapp_enabled        BOOLEAN DEFAULT FALSE
whatsapp_opted_in       BOOLEAN DEFAULT FALSE   -- explicit consent required
whatsapp_phone          TEXT                    -- E.164 format
quiet_hours_start       INTEGER DEFAULT 22      -- local hour 0-23
quiet_hours_end         INTEGER DEFAULT 7
timezone                TEXT DEFAULT 'UTC'
preferred_channel       TEXT DEFAULT 'email'    -- email | whatsapp
```

**`notification_log`** — every sent notification
```sql
id                      UUID PRIMARY KEY DEFAULT gen_random_uuid()
uid                     TEXT REFERENCES users(uid)
notification_type       TEXT    -- daily_spark | cliffhanger_return | re_engagement | etc.
channel                 TEXT    -- email | whatsapp
sent_at                 TIMESTAMPTZ DEFAULT now()
opened_at               TIMESTAMPTZ             -- populated by tracking pixel / webhook
subject                 TEXT
message_preview         TEXT    -- first 100 chars for debugging
```

**`notification_queue`** — scheduled / deferred notifications
```sql
id                      UUID PRIMARY KEY DEFAULT gen_random_uuid()
uid                     TEXT REFERENCES users(uid)
notification_type       TEXT
channel                 TEXT
scheduled_for           TIMESTAMPTZ
payload                 JSONB   -- context data for copy generation
status                  TEXT DEFAULT 'pending'  -- pending | sent | cancelled
created_at              TIMESTAMPTZ DEFAULT now()
```

### 1.3 Base service skeleton (`app/services/notification_service.py`)

```python
class NotificationService:
    async def send_notification(user, notification_type, channel, context) -> bool
    async def get_today_count(uid) -> int
    async def is_quiet_hours(uid) -> bool
    async def schedule_for_later(uid, notification_type, context, when)
    async def log_notification(uid, notification_type, channel, subject, preview)
    async def get_engagement_stats(uid) -> dict   # open rate last N notifications
```

### 1.4 New file: `app/services/copy_generator.py`
Thin wrapper around Claude Haiku to generate notification copy given a `notification_type` and user context dict. Returns `{subject, body_html, short_message}`.

---

## Phase 2 — Email Channel (SendGrid)

### 2.1 New file: `app/services/email_service.py`
- Wrap SendGrid Python SDK
- Methods: `send_transactional(to, subject, html_body, text_body)`
- Unsubscribe header injected automatically on every send (GDPR)
- Open-tracking pixel embedded for engagement tracking

### 2.2 Notification types implemented in this phase

| Type | Trigger | Copy generation |
|---|---|---|
| `daily_spark` | Scheduled 08:00 user local time | Claude Haiku — references last session topic + interest profile |
| `re_engagement` | 7 days no session | Claude Haiku — references user domain |

### 2.3 New endpoint: `POST /api/v1/notifications/trigger` (admin-only)
Manual fire for a specific user + notification type. Used for testing.

### 2.4 Requirements addition
```
sendgrid>=6.11.0
```

---

## Phase 3 — WhatsApp Channel (Twilio)

### 3.1 New file: `app/services/whatsapp_service.py`
- Wrap Twilio Python helper library
- Method: `send_whatsapp(to_e164, message)`
- Guards: `whatsapp_opted_in` must be `True` — hard-stop if not

### 3.2 Opt-in flow (two new endpoints)

```
POST /api/v1/notifications/whatsapp/opt-in
  body: { phone: "+919876543210" }
  → sends WhatsApp verification message "Reply YES to receive ECALT notifications"

POST /api/v1/notifications/whatsapp/confirm
  body: { phone: "+919876543210", code: "YES" }
  → sets whatsapp_opted_in=TRUE, stores phone in notification_preferences
```

Twilio sandbox can be used in development; production requires approved WhatsApp Business template messages.

### 3.3 Notification types implemented in this phase

| Type | Channel | Trigger |
|---|---|---|
| `daily_spark` | WhatsApp | Same scheduled trigger as email — sent if user prefers WhatsApp |
| `cliffhanger_return` | WhatsApp + Email | 2 hours after chat session ends with unresolved question |

### 3.4 Requirements addition
```
twilio>=9.0.0
```

---

## Phase 4 — Anti-Annoyance Engine

### 4.1 Daily cap enforcement (in `NotificationService`)
```python
async def can_send(uid) -> bool:
    today_count = await get_today_count(uid)
    if today_count >= 2:
        return False
    last_3_opens = await get_open_rate(uid, last_n=3)
    if last_3_opens == 0:        # 0/3 opened → cap at 1/day
        return today_count < 1
    last_5_opens = await get_open_rate(uid, last_n=5)
    if last_5_opens == 0:        # 0/5 opened → quiet mode: max 2/week
        return await get_week_count(uid) < 2
    return True
```

### 4.2 Quiet hours check
- Read `quiet_hours_start` / `quiet_hours_end` + `timezone` from `notification_preferences`
- If currently in quiet hours → insert row into `notification_queue` for next allowed time
- APScheduler worker polls `notification_queue` every 15 minutes

### 4.3 Channel fallback logic
If `last_3_opens == 0` and preferred channel is `email` → try `whatsapp` next (if opted-in), and vice-versa.

---

## Phase 5 — User Preference API

### 5.1 New endpoints under `/api/v1/notifications/preferences`

```
GET    /api/v1/notifications/preferences          → returns current preferences
PATCH  /api/v1/notifications/preferences          → update channels, quiet hours, timezone
DELETE /api/v1/notifications/preferences/email    → unsubscribe from email (one-click GDPR)
DELETE /api/v1/notifications/preferences/whatsapp → opt-out of WhatsApp
```

### 5.2 One-click unsubscribe
- Every email contains a signed unsubscribe token in the footer link
- `GET /api/v1/notifications/unsubscribe?token=<signed_token>` — no auth required, sets `email_enabled=FALSE`

---

## Phase 6 — Scheduled Triggers (APScheduler)

### 6.1 New file: `app/services/scheduler.py`
Use `APScheduler` with `AsyncIOScheduler`. Register in FastAPI lifespan.

### 6.2 Jobs

| Job | Schedule | Action |
|---|---|---|
| `daily_spark_dispatch` | Every 15 min | Query users whose local time is 08:00 ± 15min and have not received daily_spark today → send |
| `queue_processor` | Every 15 min | Process pending rows in `notification_queue` whose `scheduled_for <= now()` |
| `re_engagement_check` | Daily 09:00 UTC | Find users with last session > 7 days ago → enqueue re_engagement |
| `cliffhanger_scheduler` | Triggered by chat endpoint | When session ends with `has_cliffhanger=True` → insert queue row for +2h |

### 6.3 Requirements addition
```
apscheduler>=3.10.4
```

---

## Phase 7 — Remaining Notification Types

Implemented after Phase 6 is stable:

| Type | Notes |
|---|---|
| `connection_alert` | Requires cross-session topic analysis — AI batch job, max 3/week |
| `world_event_hook` | Requires news feed integration (NewsAPI or similar), max 2/week |
| `milestone_approach` | Hook into progress tracking — fires when user is 1-2 sessions from milestone |
| `mind_signature_ready` | Already has mind_signature endpoint — add notification hook there |
| `family_highlight` | Requires family plan detection from subscriptions — weekly summary email |

---

## Key Decisions & Constraints

- **WhatsApp requires explicit opt-in** — guarded at the service layer, never bypassed
- **SMS excluded from scope** — per spec, SMS is OTP + milestone only; milestone deferred to Phase 7
- **Copy generation** — Claude Haiku (`claude-haiku-4-5-20251001`) for all notification copy; keeps costs low for high-frequency sends
- **No mock DB in tests** — integration tests hit real Supabase test schema (consistent with project test policy)
- **Unsubscribe in one click** — GDPR-required, enforced via signed token endpoint with no auth
- **Suppression window** — 22:00–07:00 user local time; enforced before every send, not just scheduling

---

## File Manifest (new files created across all phases)

```
backend/app/services/notification_service.py   # Phase 1
backend/app/services/copy_generator.py         # Phase 1
backend/app/services/email_service.py          # Phase 2
backend/app/services/whatsapp_service.py       # Phase 3
backend/app/services/scheduler.py              # Phase 6
backend/app/api/v1/endpoints/notifications.py  # Phase 2 (grows across phases)
backend/migrations/add_notification_tables.sql # Phase 1
```

Existing files modified:
```
backend/app/core/config.py          # add SENDGRID_API_KEY, TWILIO_* vars
backend/app/api/v1/router.py        # register notifications router
backend/app/main.py                 # register APScheduler in lifespan
backend/requirements.txt            # sendgrid, twilio, apscheduler
```

---

## Starting Point

Begin with **Phase 1**: DB migration + config + base service skeleton. No external API calls yet. Confirm schema before proceeding to Phase 2.
