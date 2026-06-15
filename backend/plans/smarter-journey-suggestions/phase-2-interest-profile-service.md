# Phase 2 — Interest Profile Service

**Effort:** ~1 day  
**Risk:** Low — pure read, no API surface changes, no new tables

## What it does

Creates `app/services/interest_profile_service.py` — a single function that returns a ranked list of topics/domains for a user, derived from the data we already have. This service is not exposed as an endpoint; Phases 3 and 4 both call it internally.

## Why the data is already there

Every call to `/explore` saves a row in `journeys` with:
- `question` — the raw search string the user typed ("how does quantum entanglement work?")
- `tags` — AI-extracted topic tags (["physics", "quantum", "science"])
- `difficulty` — what level the user asked for

This is effectively a search log. Combined with `domain_mastery`, `quiz_results`, and `user_interests`, we have a rich signal without any new tracking.

## The interest profile shape

```python
@dataclass
class TopicSignal:
    topic: str            # normalised tag or domain name
    weight: float         # 0.0–1.0, higher = stronger interest / more need
    signal_type: str      # "interest" | "mastery_gap" | "quiz_struggle" | "declared"
    recency_boost: float  # decayed by days since last signal
```

```python
@dataclass  
class InterestProfile:
    uid: str
    top_topics: list[TopicSignal]   # top 10, sorted by weight desc
    preferred_difficulty: str        # "beginner" | "intermediate" | "advanced"
    age_group: str
    generated_at: datetime
```

## Signal sources and weights

| Source | How mined | Base weight |
|---|---|---|
| `journeys.tags` (recent explore searches) | All tags from journeys WHERE uid = ? and NOT is_curated, grouped and counted | 1.0 per tag occurrence, decayed by age (half-life ~14 days) |
| `journeys.question` (raw search text) | Extract noun phrases via regex; map to domain vocabulary | 0.7 per match |
| `user_interests.topics` (declared at onboarding) | Direct — each declared topic gets a baseline | 0.5 flat |
| `domain_mastery` (mastered domains) | High mastery → suggest advancement; low mastery in a touched domain → suggest reinforcement | 0.8 for `mastery_level < 0.4` on a domain the user has started, 0.6 for `mastery_level > 0.7` (level-up signal) |
| `quiz_results` (struggles) | Concepts where `is_correct = FALSE` rate > 50% in last 30 days | 0.9 (reinforcement — highest priority because explicit struggle) |
| `knowledge_nodes.strength` | Low-strength nodes in visited domains | 0.4 |

## Normalisation

1. Collect all raw signals into a `dict[topic → float]` by summing weights.
2. Apply recency decay: `weight *= exp(-days_since / 14)` so a search from yesterday outweighs one from a month ago.
3. Normalise to [0.0, 1.0] range.
4. Take top 10.

## Preferred difficulty

```python
# Count completed journeys by difficulty level
# Majority difficulty = current level; next level = preferred for advancement
completed_beginner = ...
completed_intermediate = ...
# If user has 3+ completed beginner journeys → recommend intermediate
```

## Caching

The profile is cheap to compute (5 DB queries, no AI). Cache it in memory with a 1-hour TTL using a simple `dict[uid → (profile, computed_at)]` on the service module. Invalidate on explicit call. No Redis needed.

## Function signature

```python
async def get_interest_profile(uid: str) -> InterestProfile:
    """Returns the user's ranked interest profile from all available signals.
    Cached for 1 hour per uid."""
```

## What this does NOT do

- Does not store anything — pure read and compute.
- Does not expose an API endpoint (though one could be added later for a "Your Interests" settings page).
- Does not call AI — entirely rule-based, so no token cost.
