# Phase 1 — Journey Confirmation Gate

**Goal:** Show the user the generated journey (title + description + step list) before
persisting it to the database or warming steps. If it's wrong, they reprompt — no
budget wasted on a hallucinated path.

---

## Current Flow (the problem)

```
User submits question
       ↓
POST /api/v1/explore
       ↓
generate_journey()          ← AI call
       ↓
INSERT INTO journeys        ← persisted immediately
       ↓
background: warm_journey_steps()  ← AI calls for all steps
       ↓
ExploreResponse returned to frontend
       ↓
User sees journey — but it might already be wrong
```

The journey is committed and steps are warming before the user has a chance to
confirm it represents their actual question.

---

## Target Flow

```
User submits question
       ↓
POST /api/v1/explore/preview
       ↓
generate_journey()          ← AI call (same)
       ↓
INSERT INTO journey_previews (TTL 30 min, not journeys)
       ↓
preview_token returned to frontend
       ↓
Frontend shows journey — user reads it
       ↓
  ┌────────────────────────────────────────────────┐
  │  "Does this match what you were looking for?"  │
  │                                                │
  │  [Yes, start this journey]   [No, refine it]  │
  └────────────────────────────────────────────────┘
       ↓                               ↓
POST /api/v1/explore/confirm   reprompt input (pre-filled)
(preview_token)                        ↓
       ↓                       POST /api/v1/explore/preview again
INSERT INTO journeys
background: warm_journey_steps()
Redirect → /journey/{id}
```

---

## Backend Changes

### 1. Migration — `journey_previews` table

```sql
-- migrations/NNN_journey_preview_cache.sql

CREATE TABLE IF NOT EXISTS journey_previews (
  preview_token  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  uid            text NOT NULL REFERENCES users(uid) ON DELETE CASCADE,
  question       text NOT NULL,
  journey_json   jsonb NOT NULL,
  age_group      text NOT NULL DEFAULT 'all',
  created_at     timestamptz DEFAULT now(),
  expires_at     timestamptz DEFAULT now() + INTERVAL '30 minutes'
);

CREATE INDEX IF NOT EXISTS journey_previews_uid_idx  ON journey_previews(uid);
CREATE INDEX IF NOT EXISTS journey_previews_exp_idx  ON journey_previews(expires_at);
```

A cron job or next-access cleanup removes rows where `expires_at < now()`.
Alternatively, add a DELETE WHERE expires_at < now() call at the top of the preview
endpoint (cheap, no separate worker needed).

---

### 2. `POST /api/v1/explore/preview`

**File:** `app/api/v1/endpoints/explore.py`

Same guards as the existing `explore` endpoint (auth, topic scope, budget check).
The budget check runs here, NOT on confirm — confirming a cached preview is free.

```python
@router.post("/preview", summary="Generate a journey preview (not persisted)")
async def explore_preview(
    request: ExploreRequest,
    uid: str = Depends(get_required_user),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    topic_allowed, topic_reason = check_topic_scope(request.question)
    if not topic_allowed:
        raise HTTPException(status_code=422, detail=topic_reason)

    allowed, reason = check_budget(uid)
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    try:
        journey, in_tok, out_tok = await generate_journey(
            question=request.question.strip(),
            age_group=request.age_group or "all",
            uid=uid,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("explore preview failed")
        raise HTTPException(status_code=500, detail="Failed to generate journey. Please try again.")

    record_usage(uid, in_tok, out_tok, get_config("journey")["model"], interaction_type="journey")

    # Clean up expired previews (cheap housekeeping, no worker needed)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM journey_previews WHERE expires_at < now()")
    except Exception:
        pass

    # Store preview (not journeys table)
    import json as _json
    preview_token = None
    try:
        journey_json = _json.dumps({
            "id":              journey.id,
            "question":        journey.question,
            "title":           journey.title,
            "description":     journey.description,
            "age_group":       journey.age_group,
            "difficulty":      journey.difficulty,
            "estimated_hours": journey.estimated_hours,
            "icon":            journey.icon,
            "tags":            journey.tags,
            "steps":           [s.model_dump() for s in journey.steps],
            "created_at":      journey.created_at,
        })
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO journey_previews (uid, question, journey_json, age_group)
                    VALUES (%s, %s, %s::jsonb, %s)
                    RETURNING preview_token
                    """,
                    (uid, journey.question, journey_json, journey.age_group),
                )
                preview_token = str(cur.fetchone()["preview_token"])
    except Exception:
        logger.exception("failed to store journey preview")
        raise HTTPException(status_code=500, detail="Preview storage failed")

    return {"preview_token": preview_token, "journey": journey}
```

Return shape: `{ preview_token: string, journey: Journey }`

---

### 3. `POST /api/v1/explore/confirm`

**File:** `app/api/v1/endpoints/explore.py`

Takes only the `preview_token` — no AI call, no budget charge.

```python
class ConfirmRequest(BaseModel):
    preview_token: str

@router.post("/confirm", summary="Confirm a previewed journey and persist it")
async def explore_confirm(
    request: ConfirmRequest,
    background_tasks: BackgroundTasks,
    uid: str = Depends(get_required_user),
):
    import json as _json

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT journey_json, question, age_group
                    FROM journey_previews
                    WHERE preview_token = %s AND uid = %s AND expires_at > now()
                    """,
                    (request.preview_token, uid),
                )
                row = cur.fetchone()
    except Exception:
        logger.exception("journey confirm db fetch failed")
        raise HTTPException(status_code=500, detail="Confirm failed")

    if not row:
        raise HTTPException(status_code=404, detail="Preview not found or expired. Please generate a new journey.")

    data = row["journey_json"] if isinstance(row["journey_json"], dict) else _json.loads(row["journey_json"])
    age_group = row["age_group"]

    steps = [
        JourneyStep(
            id=s["id"], title=s["title"], description=s["description"],
            type=s["type"], estimated_minutes=int(s["estimated_minutes"]),
        )
        for s in data["steps"]
    ]
    journey = Journey(
        id=data["id"], question=data["question"], title=data["title"],
        description=data["description"], age_group=data["age_group"],
        difficulty=data["difficulty"], estimated_hours=float(data["estimated_hours"]),
        steps=steps, tags=data.get("tags", []), icon=data.get("icon", "📚"),
        created_at=data["created_at"],
    )

    # Persist to journeys table
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                import json as _json2
                cur.execute(
                    """
                    INSERT INTO journeys
                        (id, uid, question, title, description, age_group, difficulty,
                         estimated_hours, steps, tags, icon, is_curated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, FALSE)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        journey.id, uid, journey.question, journey.title,
                        journey.description, journey.age_group, journey.difficulty,
                        journey.estimated_hours,
                        _json2.dumps([s.model_dump() for s in journey.steps]),
                        journey.tags, journey.icon,
                    ),
                )
                # Delete used preview
                cur.execute("DELETE FROM journey_previews WHERE preview_token = %s", (request.preview_token,))
    except Exception:
        logger.exception("failed to persist confirmed journey")
        raise HTTPException(status_code=500, detail="Failed to save journey")

    invalidate_profile(uid)
    _invalidate_recommendation_cache(uid)

    background_tasks.add_task(
        warm_journey_steps,
        journey.id, journey.steps, journey.title, journey.question, age_group, uid,
    )

    return ExploreResponse(journey=journey)
```

Register both routes on the explore router:
```python
router.post("/preview", ...)(explore_preview)
router.post("/confirm", ...)(explore_confirm)
```

---

## Frontend Changes

### `src/lib/api.ts` — two new typed wrappers

```typescript
export async function previewJourney(
  body: { question: string; age_group?: string },
  token: string
): Promise<{ preview_token: string; journey: Journey }> {
  return request('/api/v1/explore/preview', { method: 'POST', body, token })
}

export async function confirmJourney(
  preview_token: string,
  token: string
): Promise<{ journey: Journey }> {
  return request('/api/v1/explore/confirm', { method: 'POST', body: { preview_token }, token })
}
```

---

### `src/pages/Explore.tsx` — confirmation state machine

Add a new phase between "generated" and "started":

```typescript
type ExplorePhase =
  | 'idle'
  | 'loading'          // calling /preview
  | 'confirming'       // journey preview shown, awaiting user decision
  | 'confirming_save'  // calling /confirm
  | 'ready'            // journey confirmed + persisted, show full step list
  | 'error'

// State additions
const [previewToken, setPreviewToken] = useState<string | null>(null)
const [phase, setPhase] = useState<ExplorePhase>('idle')
```

**On question submit:** call `previewJourney()`, set phase → `confirming`, store `previewToken`.

**Confirmation banner** (rendered when `phase === 'confirming'`):

```tsx
<div className="glass rounded-2xl p-6 border border-violet-300/30 dark:border-violet-500/20 mb-6">
  <p className="text-slate-700 dark:text-slate-300 text-sm mb-4">
    Does this look right for what you had in mind?
  </p>
  <div className="flex flex-col sm:flex-row gap-3">
    <button
      onClick={handleConfirm}
      disabled={phase === 'confirming_save'}
      className="btn-primary flex items-center justify-center gap-2"
    >
      {phase === 'confirming_save' ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
      Yes, start this journey
    </button>
    <button
      onClick={handleRefine}
      className="btn-ghost"
    >
      Not quite — let me refine
    </button>
  </div>
</div>
```

**`handleConfirm`:** call `confirmJourney(previewToken)` → set phase → `ready`, update journey + steps.

**`handleRefine`:** clear `previewToken`, set phase → `idle`, show the `CuriosityInput` with the
current question pre-filled so the user can refine the wording.

**When phase is `ready`:** hide the confirmation banner, show `beginJourney` button and step list
(same as today's `journey && !loading` render block).

---

## What Does Not Change

- The journey generation AI call (`generate_journey()`) is identical.
- Budget is deducted on preview (same as today). Confirming is free.
- Step content warming still starts immediately on confirm, same as before.
- The `/journey/:id` page and all step/quiz/progress flows are untouched.

---

## Edge Cases

| Scenario | Behaviour |
|----------|-----------|
| User closes tab after preview | Preview expires in 30 min. No persisted journey, no harm. |
| User submits a second question before confirming the first | New preview call; old preview_token is abandoned (expires naturally). |
| Preview token expired on confirm | 404 → frontend shows "Preview expired, generating a fresh one" and re-calls `/preview`. |
| Budget exhausted mid-session | Checked on `/preview`. `/confirm` is free — no re-check needed. |
