# Plan 6 — Content & Learning Analytics

## What It Shows

A new **Content** tab in the admin panel:
- Top journey topics (what users are most curious about)
- Journey completion rate (started vs fully finished)
- Step drop-off analysis (which step do users abandon at)
- Most active conversations by message count
- Knowledge graph growth (concepts discovered per day)

---

## Backend

### New endpoint — `GET /admin/content-stats`

**Query 1 — Top journeys by engagement**
```sql
SELECT
    j.id, j.title, j.icon, j.difficulty,
    j.estimated_hours,
    j.age_group,
    COUNT(DISTINCT up.uid)              AS unique_learners,
    COUNT(up.id)                        AS total_step_completions,
    jsonb_array_length(j.steps)         AS total_steps,
    -- fully completed = user finished all steps
    COUNT(DISTINCT CASE
        WHEN step_counts.completed = jsonb_array_length(j.steps)
        THEN step_counts.uid END)       AS fully_completed_users,
    ROUND(
        COUNT(DISTINCT CASE
            WHEN step_counts.completed = jsonb_array_length(j.steps)
            THEN step_counts.uid END
        )::numeric /
        NULLIF(COUNT(DISTINCT up.uid), 0) * 100
    , 1)                                AS completion_pct
FROM journeys j
LEFT JOIN user_progress up ON up.journey_id = j.id
LEFT JOIN (
    SELECT journey_id, uid, COUNT(*) AS completed
    FROM user_progress
    GROUP BY journey_id, uid
) step_counts ON step_counts.journey_id = j.id AND step_counts.uid = up.uid
GROUP BY j.id, j.title, j.icon, j.difficulty, j.estimated_hours, j.age_group
HAVING COUNT(DISTINCT up.uid) > 0
ORDER BY unique_learners DESC
LIMIT 20
```

**Query 2 — Step drop-off for a specific journey**

(called with `?journey_id=xxx` query param — optional, admin picks a journey to drill in)
```sql
SELECT
    up.step_id,
    COUNT(DISTINCT up.uid)              AS completions
FROM user_progress up
WHERE up.journey_id = %s
GROUP BY up.step_id
ORDER BY completions DESC
```

**Query 3 — Overall completion rate summary**
```sql
SELECT
    COUNT(DISTINCT journey_id)          AS journeys_started,
    COUNT(DISTINCT uid)                 AS users_with_progress,
    ROUND(AVG(pct)::numeric, 1)         AS avg_completion_pct
FROM (
    SELECT
        up.uid, up.journey_id,
        COUNT(up.step_id)::float /
        NULLIF(jsonb_array_length(j.steps), 0) * 100 AS pct
    FROM user_progress up
    JOIN journeys j ON j.id = up.journey_id
    GROUP BY up.uid, up.journey_id, j.steps
) sub
```

**Query 4 — Most active conversations (last 30 days)**
```sql
SELECT
    c.id, c.title, c.uid,
    u.email, u.display_name,
    COUNT(cm.id)                        AS message_count,
    MAX(cm.created_at)                  AS last_message_at
FROM conversations c
JOIN conversation_messages cm ON cm.conversation_id = c.id
JOIN users u ON u.uid = c.uid
WHERE c.started_at >= now() - interval '30 days'
GROUP BY c.id, c.title, c.uid, u.email, u.display_name
ORDER BY message_count DESC
LIMIT 20
```

**Query 5 — Knowledge graph growth (concepts discovered per day, last 14 days)**
```sql
SELECT
    discovered_at::date         AS day,
    COUNT(*)                    AS new_concepts,
    COUNT(DISTINCT uid)         AS unique_users
FROM knowledge_nodes
WHERE discovered_at >= now() - interval '14 days'
GROUP BY day
ORDER BY day
```

**Response shape**
```json
{
  "top_journeys": [
    { "id": "...", "title": "How does photosynthesis work?",
      "icon": "🌿", "difficulty": "beginner",
      "unique_learners": 28, "total_steps": 6,
      "fully_completed_users": 11, "completion_pct": 39.3 }
  ],
  "completion_summary": {
    "journeys_started": 45,
    "users_with_progress": 38,
    "avg_completion_pct": 41.2
  },
  "top_conversations": [
    { "id": "...", "title": "Quantum entanglement explained",
      "uid": "...", "email": "...",
      "message_count": 34, "last_message_at": "2026-05-25T..." }
  ],
  "knowledge_growth": [
    { "day": "2026-05-20", "new_concepts": 42, "unique_users": 9 }
  ]
}
```

---

## Frontend

### New tab
Add `{ id: 'content', label: 'Content' }` to `TABS`.

### UI layout

```
Completion Summary
  45 journeys started  ·  38 users with progress  ·  41.2% avg completion

Top Journeys (by learners)
  🌿 How does photosynthesis work?   28 learners   39.3% complete   beginner
     [████████████████░░░░░░░░░░░]
  ⚛️  Quantum entanglement           14 learners   21.4% complete   advanced
     [██████░░░░░░░░░░░░░░░░░░░░░]

  [ clicking a row shows step drop-off detail ]

Most Active Conversations (last 30 days)
  "Quantum entanglement explained"   alice@...   34 messages   May 25
  "History of the Roman Empire"      bob@...     28 messages   May 24

Knowledge Graph Growth (last 14 days)
  [small bar chart — bars = new concepts per day]
  May 20  ████  42 concepts
  May 21  ██    19 concepts
```

**Journey row expansion** — clicking a journey row fetches `GET /admin/content-stats?journey_id=xxx` and shows a mini step-completion bar per step (step 1: 28, step 2: 24, step 3: 18... — shows where users drop off).

**Completion bar** — a horizontal progress bar showing `fully_completed / unique_learners`. Color: violet for high completion, amber for medium, rose for low.

---

## Notes

- `jsonb_array_length(j.steps)` works because `steps` is stored as a JSONB array in the `journeys` table.
- Average completion % of 40%+ is healthy for a self-directed learning app. Below 20% suggests the journeys are too long or too hard.
- The step drop-off query (Query 2) is the most actionable for content improvement — if step 3 has 50% of the completions of step 1, that step is a blocker.
- `knowledge_nodes` tracks concepts a user has encountered. Growth in unique users discovering concepts is a good proxy for learning depth.
- Top conversations are useful for understanding what users actually want to talk about — informs journey creation and curated content strategy.
