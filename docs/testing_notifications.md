# Testing Notifications — ECALT

A complete guide to using `scripts/test_notification.py` to test, preview, and diagnose the notification system without touching the scheduler.

---

## Prerequisites

```bash
cd backend
source .venv/bin/activate
```

Your `.env` must have the following populated:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection (Supabase pooler) |
| `TWILIO_ACCOUNT_SID` | Twilio credentials |
| `TWILIO_AUTH_TOKEN` | Twilio credentials |
| `TWILIO_WHATSAPP_FROM` | Sender number e.g. `whatsapp:+14155238886` |
| `SENDGRID_API_KEY` | SendGrid credentials |
| `SENDGRID_FROM_EMAIL` | Verified sender e.g. `hello@ecalt.app` |
| `NOTIFICATIONS_WHATSAPP_ENABLED` | `true` / `false` |
| `NOTIFICATIONS_EMAIL_ENABLED` | `true` / `false` |
| `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` | Copy generation (Haiku / gpt-4.1-nano) |
| `FRONTEND_URL` | Appended to WhatsApp messages e.g. `https://ecalt.vercel.app` |

The script **bypasses** the daily cap and quiet-hours gate. It respects channel kill-switches unless you pass `--force-channel`.

---

## Step 0 — One-time WhatsApp opt-in setup

The script will refuse to send a WhatsApp message if the user does not have a `notification_preferences` row with `whatsapp_opted_in = TRUE`. Run this once per user (or after a DB wipe):

```bash
python scripts/test_notification.py \
  --email you@example.com \
  --setup-whatsapp +919876543210
```

This upserts the row and exits immediately. The phone number must be in E.164 format (`+<country_code><number>`).

---

## Step 1 — Check channel status

Before sending anything, verify which channels are enabled:

```bash
python scripts/test_notification.py --status
```

Output:

```
Channel status (from .env):
  email        ✗ disabled
  whatsapp     ✓ enabled

Active: whatsapp
```

If all channels show `✗ disabled`, no sends will go through unless you use `--force-channel`.

---

## Step 2 — Inspect the user's live data

The script pulls real DB data (streak, topics, journeys, mastery) so generated messages are realistic. To see exactly what data it would use:

```bash
python scripts/test_notification.py --email you@example.com --user-state
```

Output:

```
── User state: Biswambar ──────────────────────────────
  Streak                   7
  Days inactive            0
  Top domain               physics
  Mastery %                42
  Topics                   physics, history, astronomy
  Journey in progress      How DNA Actually Works
  Steps remaining          2
  New concepts (7d)        5
  Active domains (7d)      2
  Journeys touched (7d)    1
  WhatsApp phone           +919876543210
  WhatsApp opted in        True
```

If a field is missing, the script falls back to its hardcoded default for that notification type.

---

## Step 3 — List all notification types

```bash
python scripts/test_notification.py --list-types
```

Output shows every type grouped by category, plus its default context values:

```
Core:
  daily_spark               {"topics": "physics, history", "angle": "physics"}
  re_engagement             {"domain": "physics", "days_inactive": 10}
  cliffhanger_return        {"topic": "quantum entanglement"}

Streak:
  streak_at_risk            {"streak_days": 7}
  streak_lost               {"streak_days": 7}
  streak_milestone          {"streak_days": 7}

Progress:
  journey_almost_done       {"journey_title": "How DNA Actually Works", "steps_remaining": 1}
  mind_signature_nudge      {"domain": "physics", "mastery_pct": 42}
  mind_signature_ready      {"domain": "biology"}

Discovery:
  connection_alert          {"topic_a": "music", "topic_b": "mathematics", ...}
  world_event_hook          {"event": "James Webb telescope new image", "topic": "astronomy"}

Digest:
  weekly_digest             {"new_concepts": 8, "active_domains": 3, ...}
  family_highlight          {"summary": "..."}
```

---

## Sending a single notification

### Default (auto-picks first enabled channel)

```bash
python scripts/test_notification.py --email you@example.com
```

Sends `daily_spark` via the first enabled channel (whatsapp or email).

### Specify type and channel

```bash
python scripts/test_notification.py \
  --email you@example.com \
  --type streak_at_risk \
  --channel whatsapp
```

### All 13 types at once

```bash
python scripts/test_notification.py --email you@example.com --all
```

Iterates every type in order, waits 1 second between sends to avoid Twilio/SendGrid rate limits, then prints a summary table.

---

## Previewing copy without sending

`--preview` generates the AI copy and prints it, but does **not** deliver it. Use this to iterate on message quality without burning Twilio/SendGrid credits.

### Preview one type

```bash
python scripts/test_notification.py \
  --email you@example.com \
  --type cliffhanger_return \
  --preview
```

Output:

```
── cliffhanger_return (preview) ──
  → Generating copy ...
  Subject      : You left something unresolved...
  Short message: Biswambar, did you ever figure out why quantum entanglement breaks locality? → https://ecalt.vercel.app/learn
  HTML body    :
    <p>Hey Biswambar, ...</p> ...
```

### Preview all 13 types at once

```bash
python scripts/test_notification.py --email you@example.com --all --preview
```

Prints copy for every type in sequence — useful for a full audit without sending anything.

---

## Overriding context fields

By default the script layers context in this priority order (highest wins):

```
hardcoded defaults → live DB data → --context override
```

Use `--context` to inject or override specific fields as a JSON string:

```bash
# Simulate a 30-day streak
python scripts/test_notification.py \
  --email you@example.com \
  --type streak_at_risk \
  --context '{"streak_days": 30}'

# Test re-engagement for a specific domain
python scripts/test_notification.py \
  --email you@example.com \
  --type re_engagement \
  --context '{"domain": "astronomy", "days_inactive": 14}'

# Simulate a journey almost done
python scripts/test_notification.py \
  --email you@example.com \
  --type journey_almost_done \
  --context '{"journey_title": "The Physics of Black Holes", "steps_remaining": 1}'

# Simulate a connection insight
python scripts/test_notification.py \
  --email you@example.com \
  --type connection_alert \
  --context '{"topic_a": "jazz", "topic_b": "mathematics", "connection": "both rely on structured improvisation within constraints"}'
```

---

## Using hardcoded defaults (skip live DB)

If you want repeatable results regardless of actual user state:

```bash
python scripts/test_notification.py \
  --email you@example.com \
  --type weekly_digest \
  --no-real-context
```

---

## Force-sending on a disabled channel

If a channel is turned off in `.env` but you need to test it anyway:

```bash
python scripts/test_notification.py \
  --email you@example.com \
  --channel email \
  --force-channel
```

This overrides `NOTIFICATIONS_EMAIL_ENABLED=false` for this one send.

---

## Notification types reference

| Type | Group | Required context keys | What it does |
|---|---|---|---|
| `daily_spark` | Core | `topics`, `angle` | Personalized daily curiosity nudge based on their topics |
| `re_engagement` | Core | `domain`, `days_inactive` | Pulls back an inactive user with a domain-specific hook |
| `cliffhanger_return` | Core | `topic` | Reminds user of an unresolved conversation they left |
| `streak_at_risk` | Streak | `streak_days` | Warm nudge before a streak breaks tonight |
| `streak_lost` | Streak | `streak_days` | Compassionate "start fresh" message after streak breaks |
| `streak_milestone` | Streak | `streak_days` | Celebratory message on hitting a milestone |
| `journey_almost_done` | Progress | `journey_title`, `steps_remaining` | Motivates them across the finish line |
| `mind_signature_nudge` | Progress | `domain`, `mastery_pct` | Teases the Mind Signature they're close to earning |
| `mind_signature_ready` | Progress | `domain` | Celebrates a newly earned Mind Signature |
| `connection_alert` | Discovery | `topic_a`, `topic_b`, `connection` | Cross-domain insight connecting two of their topics |
| `world_event_hook` | Discovery | `event`, `topic` | Links a real-world event to their learning topic |
| `weekly_digest` | Digest | `new_concepts`, `active_domains`, `domains`, `journeys_touched` | Weekly learning summary |
| `family_highlight` | Digest | `summary` | Family-mode weekly highlight |

---

## Common workflows

### "I want to test WhatsApp end-to-end for the first time"

```bash
# 1. Seed the opt-in
python scripts/test_notification.py \
  --email you@example.com \
  --setup-whatsapp +919876543210

# 2. Check status
python scripts/test_notification.py --status

# 3. Check user state
python scripts/test_notification.py --email you@example.com --user-state

# 4. Preview a message first
python scripts/test_notification.py \
  --email you@example.com \
  --type daily_spark \
  --channel whatsapp \
  --preview

# 5. Send it
python scripts/test_notification.py \
  --email you@example.com \
  --type daily_spark \
  --channel whatsapp
```

### "I want to review what all 13 messages look like before launch"

```bash
python scripts/test_notification.py --email you@example.com --all --preview
```

### "I want to test email even though it's disabled"

```bash
python scripts/test_notification.py \
  --email you@example.com \
  --type weekly_digest \
  --channel email \
  --force-channel
```

### "I want to simulate a specific scenario (30-day streak at risk)"

```bash
python scripts/test_notification.py \
  --email you@example.com \
  --type streak_at_risk \
  --context '{"streak_days": 30}' \
  --preview
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No user found with email` | User hasn't signed in yet | Sign in once via the app |
| `User not opted in to WhatsApp` | Missing `notification_preferences` row | Run `--setup-whatsapp PHONE` |
| `✗ WhatsApp disabled` | `NOTIFICATIONS_WHATSAPP_ENABLED=false` | Add `--force-channel` or enable in `.env` |
| `Same To and From` Twilio error | `TWILIO_WHATSAPP_FROM` matches user's phone | Set `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886` (sandbox) |
| Copy generates but URL missing | `FRONTEND_URL` not set in `.env` | Add `FRONTEND_URL=https://ecalt.vercel.app` |
| `generate_copy failed` in logs | AI provider key missing or quota exceeded | Check `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| `Could not fetch real context` warning | DB not reachable or tables missing | Run migrations: `psql $DATABASE_URL < migrations/add_notification_log_and_queue.sql` |
| Email sends but lands in spam | SendGrid sender not verified | Verify domain in SendGrid dashboard |
