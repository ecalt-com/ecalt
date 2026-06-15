# Phase 4 — Smarter Post-Completion Suggestions

**Effort:** ~1 day  
**Risk:** Low — upgrades existing `pick_suggestions` in `suggestion_service.py`, no schema changes

## What it does

The current post-completion suggestions (`GET /journeys/{id}/suggestions`) use only tag/title overlap between the finished journey and the candidate pool. This phase upgrades the algorithm to use the full interest profile from Phase 2, and adds a "Resume" slot for an in-progress journey the user has abandoned.

## Current algorithm problems

1. It only looks at the just-finished journey's tags — ignores everything else the user has done.
2. `pick_suggestions` scores by `_tag_overlap(source, j)` — a static count with no weighting.
3. If a user has a half-finished journey on a closely related topic, it never surfaces (excluded by `started_ids`).
4. The "next level" generation happens on every completion even if a highly relevant intermediate journey already exists in the catalogue but was filtered out by the duplicate check.

## Changes to `suggestion_service.py`

### `pick_suggestions` signature upgrade

```python
def pick_suggestions(
    source: Journey,
    pool: list[Journey],
    started_ids: set[str],
    authored_ids: set[str],
    curated_ids: set[str] | None = None,
    interest_profile: InterestProfile | None = None,   # NEW
    in_progress: list[JourneyWithProgress] | None = None,  # NEW
) -> tuple[Journey | None, list[Journey], Journey | None]:
    # returns (next_level, similar[≤3], resume_suggestion | None)
```

### Weighted scoring for `similar` candidates

Replace the sort key `_tag_overlap(source, j)` with a composite score:

```python
def _candidate_score(j: Journey, source: Journey, profile: InterestProfile | None) -> float:
    score = _tag_overlap(source, j) * 0.5   # existing signal, kept but weighted

    if profile:
        for signal in profile.top_topics[:5]:
            if signal.topic in {t.lower() for t in j.tags}:
                score += signal.weight * 0.4

        # Same difficulty as user's preferred → small bonus
        if j.difficulty == profile.preferred_difficulty:
            score += 0.15

    # Curated journeys are higher quality on average
    if curated_ids and j.id in curated_ids:
        score += 0.1

    return score
```

### "Resume" slot

Post-completion is a good moment to surface an abandoned journey. Add a third return value:

```python
resume = None
if in_progress:
    # Pick the in-progress journey most topically related to what was just finished
    in_progress_sorted = sorted(
        in_progress,
        key=lambda j: _tag_overlap(source, j),
        reverse=True,
    )
    resume = in_progress_sorted[0] if in_progress_sorted else None
```

The `SuggestionsResponse` in `journeys.py` gains a `resume` field:

```python
class SuggestionsResponse(BaseModel):
    next_level: Optional[Journey] = None
    similar: list[Journey] = []
    next_level_generated: bool = False
    resume: Optional[JourneyWithProgress] = None   # NEW
```

### Quiz-struggle reinforcement in `similar`

After the main `similar` list is filled (up to 3), if there are fewer than 2 topically overlapping results and the interest profile has quiz-struggle signals, inject one reinforcement candidate:

```python
if len(similar) < 2 and profile:
    struggle_topics = [s.topic for s in profile.top_topics if s.signal_type == "quiz_struggle"]
    for topic in struggle_topics:
        reinforcement = _find_reinforcement(topic, pool, started_ids, similar)
        if reinforcement:
            similar.append(reinforcement)
            break
```

`_find_reinforcement` finds the highest-scoring journey whose tags contain the struggle topic and difficulty ≤ source difficulty.

### Changes in `journeys.py` — `journey_suggestions` endpoint

1. Call `get_interest_profile(uid)` from Phase 2 (async, cached).
2. Fetch in-progress journeys (same query as Phase 1's list endpoint).
3. Pass both to `pick_suggestions`.
4. Return the `resume` field in `SuggestionsResponse`.

## Frontend changes (document only — see frontend plan)

- Post-completion card already shows next_level + similar.
- Add a "Resume where you left off" card if `resume` is non-null — visually distinct (lighter card, progress bar visible).
- The resume card appears between next_level and similar.

## What this does NOT do

- Does not change when generation triggers (still only generates if `source_completed` and no catalogue next_level found).
- Does not add a new endpoint — purely internal algorithm upgrade.
- The `started_ids` exclusion stays — in-progress journeys are excluded from `similar` and `next_level`. Only the explicit `resume` slot can surface them.

## Acceptance criteria

- Completing a DNA journey when the user has also searched for CRISPR and genetics → `similar` includes a genetics/molecular biology journey even if the tag overlap with DNA is only 1.
- If the user has a half-finished "Machine Learning" journey and completes an "AI Ethics" journey, the resume slot returns the ML journey.
- A user with 3 quiz failures on "gradient descent" gets a reinforcement journey in `similar` when completing the ML journey.
- The response schema is backwards-compatible — `resume: null` when there's nothing to resume, no existing field removed.
