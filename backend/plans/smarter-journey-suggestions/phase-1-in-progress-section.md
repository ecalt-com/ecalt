# Phase 1 — Surface In-Progress Journeys

**Effort:** ~1 day  
**Risk:** Low — read-only DB queries, additive response fields, no schema changes

## What it does

Adds a "Continue Learning" section to the journey tab. Any journey where the user has completed at least one step but not all steps shows up here with a progress bar.

Currently `GET /journeys` returns raw journey objects with no progress state. The frontend has no way to distinguish "started" from "never touched."

## Backend changes

### `app/api/v1/endpoints/journeys.py` — `list_journeys`

After fetching `user_journeys`, run a single extra query to get per-journey step counts:

```sql
SELECT journey_id,
       COUNT(DISTINCT step_id) AS steps_done
FROM user_progress
WHERE uid = %s
GROUP BY journey_id
```

Add two new optional fields to the `Journey` schema (or a thin wrapper):

```python
class JourneyWithProgress(Journey):
    steps_done: int = 0          # how many steps the user completed
    # total_steps is already len(journey.steps)
```

Return a new top-level `in_progress` list in `JourneysResponse` — journeys where `0 < steps_done < total_steps`. Keep the existing `journeys` list (user + curated) unchanged so nothing breaks.

### `app/models/schemas.py` — `JourneysResponse`

```python
class JourneysResponse(BaseModel):
    journeys: list[Journey]
    in_progress: list[JourneyWithProgress] = []  # new
    total: int
```

The `in_progress` list is drawn from `user_journeys` only (not curated), sorted by most recently active (`MAX(completed_at)` from `user_progress`).

## Frontend changes (document only — see frontend plan)

- Add a "Continue Learning" horizontal scroll section above the existing journey grid.
- Each card shows the journey icon, title, and a thin progress bar (`steps_done / total_steps`).
- Tapping a card opens the journey at the first incomplete step (already possible since steps are ordered).
- If `in_progress` is empty, the section is hidden — no empty state needed.

## What this does NOT do

- Does not change how a journey is marked "complete" (that's already tracked via `user_progress`).
- Does not reorder the main journey list — curated journeys stay at the bottom as before.

## Acceptance criteria

- A journey with 2/7 steps done appears in `in_progress` with `steps_done: 2`.
- A journey with 0 steps done does NOT appear in `in_progress`.
- A journey with all steps done does NOT appear in `in_progress` (it's finished).
- The existing `journeys` list is unchanged — no regressions.
