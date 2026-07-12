# Phase 3 — Frontend changes required

Backend Phase 3 (parent dashboard visibility) is implemented: per-child overview and
activity endpoints, a gated transcript endpoint, a child-facing transparency
endpoint, and a weekly family digest email (scheduler job `family_digest_dispatch`,
Sundays 17:00 UTC — no frontend work needed for the email itself).

All `/family/children/...` endpoints require the caller to be the child's linked
parent (403 otherwise). Timestamps are ISO strings.

---

## 1. Child detail page — `/family/child/:uid` (new)

### Overview tab

`GET /api/v1/family/children/{uid}/overview` →

```jsonc
{
  "child": { "display_name": "Kid", "streak_days": 3, "last_active_date": "…",
             "created_at": "…", "account_status": "active",
             "age_group_flag": "teen", "paused": false },
  "totals": { "journeys": 12, "steps_completed": 48,
              "knowledge_nodes": 31, "conversations": 7 },
  "quiz":   { "total": 40, "correct": 31, "last_7_days": 6 },
  "top_domains": [ { "domain": "physics", "mastery_level": 0.62, "concept_count": 9 }, … ],
  "recent_journeys": [ { "id": "…", "title": "…", "icon": "…", "created_at": "…",
                         "total_steps": 10, "completed_steps": 4,
                         "last_progress_at": "…" }, … ]
}
```

Suggested layout: stat cards (streak, steps, quiz accuracy = correct/total, knowledge
nodes), a domain chip list, and journey cards with progress bars
(`completed_steps / total_steps`). Passport page components are a good visual base.

### Activity tab

`GET /api/v1/family/children/{uid}/activity?days=30` (days 1–90) →

```jsonc
{
  "days": 30,
  "steps_completed":  [ { "completed_at": "…", "step_id": "…", "journey_id": "…", "journey_title": "…" } ],
  "journeys_started": [ { "id": "…", "title": "…", "question": "…", "created_at": "…" } ],
  "quiz_answers":     [ { "concept": "…", "is_correct": true, "difficulty": "…", "answered_at": "…" } ],
  "conversations":    [ { "id": "…", "title": "…", "started_at": "…", "last_active": "…", "message_count": 12 } ],
  "transcripts_available": false
}
```

Merge into one reverse-chronological timeline, or keep sections. Conversations show
**titles + message counts only**. If `transcripts_available` is true, titles link to:

`GET /api/v1/family/children/{uid}/conversations/{conversation_id}` →
`{ "id", "title", "started_at", "messages": [ { "role", "content", "created_at" } ] }`
— 403 `transcripts_not_enabled` otherwise (managed under-13s get transcripts; teens
are summaries-only until the Phase 4 family setting exists).

### Consent tab

Already documented in `phase2-frontend-changes.md`
(`GET /family/children/{uid}/consent`).

## 2. Teen transparency banner (child-facing, required)

`GET /api/v1/family/my-family` (any authenticated user) →

```jsonc
{ "linked": false }
// or
{
  "linked": true, "parent_name": "…", "managed": true,
  "parent_can_see": {
    "topics_and_journeys": true, "progress_and_streaks": true,
    "quiz_scores": true, "conversation_titles": true,
    "full_conversations": false
  }
}
```

When `linked` is true, render a section in `Profile.tsx` (and optionally a one-time
dismissible note in `Learn.tsx`): "Your account is linked to {parent_name}'s family.
They can see: topics you explore, your progress and streaks, quiz scores, and
conversation titles[, and full conversations]." This disclosure is a UK Children's
Code expectation and standard practice (Family Link does the same) — don't skip it.

## 3. Family dashboard list (Phase 1 doc) — link each child card to `/family/child/:uid`.
