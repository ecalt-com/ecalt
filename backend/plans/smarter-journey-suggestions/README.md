# Smarter Journey Suggestions — Phased Plan

Status: **DRAFT**
Created: 2026-06-15

## Problem

The journey tab currently shows two flat lists: the user's explore-generated journeys and 6 hardcoded curated ones. There is no sense of what the user is in the middle of, no personalisation beyond post-completion suggestions, and the rich data already sitting in the DB (explore questions, domain mastery, quiz results, knowledge nodes) is completely unused for recommendation.

## Goals

1. Surface journeys the user started but hasn't finished — in a "Continue Learning" section on the journey tab.
2. Build an interest profile from the user's existing explore searches, completed courses, quiz performance and domain mastery.
3. Use that profile to serve personalised recommendations ("Picked for You") without requiring the user to complete a journey first.
4. Upgrade the post-completion suggestion algorithm to leverage the same signals.

## Data available (no new tables needed for Phases 1–3)

| Table | Signal |
|---|---|
| `journeys` (`uid`, `question`, `tags`, `difficulty`, `is_curated`) | Explore search intent — every explore call mints a row with the raw question |
| `user_progress` (`uid`, `journey_id`, `step_id`, `completed_at`) | Which steps, in which journeys, the user has touched |
| `domain_mastery` (`uid`, `domain`, `mastery_level`, `learning_velocity`) | How deeply the user knows each domain |
| `knowledge_nodes` (`uid`, `concept`, `domain`, `strength`) | Concept-level granularity |
| `quiz_results` (`uid`, `concept`, `is_correct`, `difficulty`, `journey_id`) | Where the user struggles — reinforcement targets |
| `user_interests` (`uid`, `topics`, `age_group`) | Self-declared interests from onboarding |
| `cognitive_fingerprints` (`uid`, `fingerprint`) | Learning style already computed |

## Phases

- [Phase 1](phase-1-in-progress-section.md) — Surface in-progress journeys in the tab
- [Phase 2](phase-2-interest-profile-service.md) — Build an interest profile from existing data
- [Phase 3](phase-3-recommendations-endpoint.md) — "Picked for You" recommendation section
- [Phase 4](phase-4-smarter-post-completion.md) — Upgrade post-completion suggestion algorithm
