"""
Post-completion journey suggestions — phase 4 of the journey UX overhaul.

Given a finished journey, suggest (a) the next level of the same course and
(b) up to three similar courses — all guaranteed new to the user: anything
they completed, started, or authored is excluded, and near-duplicates of
those (the /explore flow mints many ~identical journeys) are filtered out
by title/tag similarity.
"""
import json
import logging
import re

from app.core.database import get_db
from app.models.schemas import Journey
from app.services.ai_service import generate_journey
from app.services.provider_service import get_config
from app.services.subscription_service import check_budget, record_usage

logger = logging.getLogger(__name__)

_DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced"]

# Common filler in AI-generated journey titles — kept out of similarity tokens
# so "Harmonies of the Future: Crafting AI Music" ≈ "Harmonizing with Machines:
# AI in Music Creation" still registers as a near-duplicate.
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "with", "for",
    "your", "you", "into", "from", "how", "what", "why", "does", "is",
    "journey", "world", "guide", "introduction", "exploring", "discovering",
    "understanding", "mastering", "unleashing", "navigating", "crafting",
    "creating", "future", "tomorrow", "odyssey",
}

DUPLICATE_THRESHOLD = 0.6      # title+tag token similarity
TAG_DUPLICATE_THRESHOLD = 0.7  # tag-set similarity — same tag profile = same course
MAX_SIMILAR = 3


def next_difficulty(difficulty: str) -> str | None:
    try:
        i = _DIFFICULTY_ORDER.index(difficulty)
    except ValueError:
        return None
    return _DIFFICULTY_ORDER[i + 1] if i + 1 < len(_DIFFICULTY_ORDER) else None


def _tokens(journey: Journey) -> set[str]:
    """Normalized title+tag tokens. Tokens are truncated to 6 chars as a crude
    stem so 'Harmonies'/'Harmonizing' or 'Creation'/'Creativity' coincide —
    that's what catches the AI-generated near-duplicate titles in prod data.
    """
    text = f"{journey.title} {' '.join(journey.tags)}"
    return {
        t[:6] for t in re.findall(r"[a-z0-9]+", text.lower())
        if len(t) >= 2 and t not in _STOPWORDS
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tag_set(journey: Journey) -> set[str]:
    return {t.strip().lower() for t in journey.tags if t.strip()}


def is_near_duplicate(journey: Journey, others: list[Journey]) -> bool:
    """A journey is a repeat if its title reads the same OR its tag profile is
    essentially identical to something the user has already seen/been offered.
    The second clause is what stops 'yet another beginner AI-music course'
    from being suggested right after finishing one."""
    toks = _tokens(journey)
    tags = _tag_set(journey)
    for o in others:
        if _jaccard(toks, _tokens(o)) >= DUPLICATE_THRESHOLD:
            return True
        if _jaccard(tags, _tag_set(o)) >= TAG_DUPLICATE_THRESHOLD:
            return True
    return False


def _tag_overlap(a: Journey, b: Journey) -> int:
    return len({t.lower() for t in a.tags} & {t.lower() for t in b.tags})


def _profile_score(j: Journey, profile) -> float:
    """Weighted score boost from the user's interest profile."""
    if profile is None:
        return 0.0
    j_tags = {t.lower() for t in j.tags}
    score = 0.0
    for sig in profile.top_topics[:5]:
        if sig.topic in j_tags:
            score += float(sig.weight) * 0.4
    return score


def _find_reinforcement(
    topic: str,
    pool: list[Journey],
    started_ids: set[str],
    already_picked: list[Journey],
    max_difficulty: str,
) -> Journey | None:
    """Find the best candidate to reinforce a topic the user struggles with."""
    diff_rank = {d: i for i, d in enumerate(_DIFFICULTY_ORDER)}
    cap = diff_rank.get(max_difficulty, 2)
    candidates = [
        j for j in pool
        if j.id not in started_ids
        and j not in already_picked
        and topic in {t.lower() for t in j.tags}
        and diff_rank.get(j.difficulty, 2) <= cap
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda j: _tag_overlap_raw(j, topic), reverse=True)
    return candidates[0]


def _tag_overlap_raw(j: Journey, topic: str) -> int:
    return 1 if topic in {t.lower() for t in j.tags} else 0


def pick_suggestions(
    source: Journey,
    pool: list[Journey],
    started_ids: set[str],
    authored_ids: set[str],
    curated_ids: set[str] | None = None,
    interest_profile=None,
    in_progress: list | None = None,
) -> tuple[Journey | None, list[Journey], Journey | None]:
    """Returns (next_level | None, similar[≤3], resume | None).

    - started/authored journeys and the source never appear in next_level or similar.
    - next_level may reuse an authored-but-unstarted journey.
    - near-duplicates of anything the user has seen are dropped.
    - resume: the most topically related in-progress journey (shown separately).
    - interest_profile boosts scoring with the user's full signal history.
    """
    curated_ids = curated_ids or set()
    seen = [j for j in pool if j.id in started_ids or j.id in authored_ids or j.id == source.id]

    # ── Next level of the same course ──────────────────────────────────────
    target_difficulty = next_difficulty(source.difficulty)
    next_level = None
    if target_difficulty:
        source_toks = _tokens(source)
        candidates = [
            j for j in pool
            if j.id not in started_ids and j.id != source.id
            and j.difficulty == target_difficulty
            and (_tag_overlap(source, j) >= 2 or _jaccard(source_toks, _tokens(j)) >= 0.5)
        ]
        candidates.sort(
            key=lambda j: (
                _tag_overlap(source, j) + _profile_score(j, interest_profile),
                j.id in curated_ids,
                j.created_at or "",
            ),
            reverse=True,
        )
        next_level = candidates[0] if candidates else None

    # ── Similar courses ────────────────────────────────────────────────────
    sim_candidates = [
        j for j in pool
        if j.id not in started_ids and j.id not in authored_ids and j.id != source.id
        and (next_level is None or j.id != next_level.id)
    ]
    sim_candidates.sort(
        key=lambda j: (
            _tag_overlap(source, j) + _profile_score(j, interest_profile),
            j.difficulty == source.difficulty,
            j.id in curated_ids,
            j.created_at or "",
        ),
        reverse=True,
    )

    taken: list[Journey] = seen + ([next_level] if next_level else [])
    similar: list[Journey] = []
    for require_overlap in (True, False):
        for j in sim_candidates:
            if len(similar) >= MAX_SIMILAR:
                break
            if j in similar:
                continue
            if require_overlap and _tag_overlap(source, j) == 0:
                continue
            if not require_overlap and _tag_overlap(source, j) > 0:
                continue
            if is_near_duplicate(j, taken):
                continue
            similar.append(j)
            taken.append(j)

    # ── Quiz-struggle reinforcement (inject if similar list is thin) ────────
    if len(similar) < 2 and interest_profile is not None:
        struggle_topics = [
            s.topic for s in interest_profile.top_topics
            if s.signal_type == "quiz_struggle"
        ]
        for topic in struggle_topics:
            reinforcement = _find_reinforcement(topic, pool, started_ids, similar + ([next_level] if next_level else []), source.difficulty)
            if reinforcement and not is_near_duplicate(reinforcement, taken):
                similar.append(reinforcement)
                taken.append(reinforcement)
                break

    # ── Resume: most topically related in-progress journey ─────────────────
    resume = None
    if in_progress:
        in_progress_sorted = sorted(
            in_progress,
            key=lambda j: _tag_overlap(source, j),
            reverse=True,
        )
        resume = in_progress_sorted[0] if in_progress_sorted else None

    return next_level, similar, resume


def _persist_journey(journey: Journey, uid: str) -> None:
    """Save a generated journey like /explore does (non-fatal on failure)."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
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
                        json.dumps([s.model_dump() for s in journey.steps]),
                        journey.tags,
                        journey.icon,
                    ),
                )
    except Exception:
        logger.exception("failed to persist suggested journey", extra={"journey_id": journey.id})


async def generate_next_level(uid: str, source: Journey) -> Journey | None:
    """Generate the next-difficulty journey for a topic the user just finished.

    Budget-gated: returns None (never raises 402) when the user is out of
    budget, so the suggestions endpoint still returns the similar list.
    """
    target_difficulty = next_difficulty(source.difficulty)
    if not target_difficulty:
        return None

    allowed, _reason = check_budget(uid)
    if not allowed:
        return None

    completed_topics = ", ".join(s.title for s in source.steps[:12])
    question = (
        f"{source.question} — LEVEL UP: the learner has just completed the "
        f"{source.difficulty} journey \"{source.title}\" (steps covered: {completed_topics}). "
        f"Create the {target_difficulty} continuation that builds on that foundation "
        f"without repeating it."
    )

    try:
        journey, in_tok, out_tok = await generate_journey(
            question=question,
            age_group=source.age_group,
            uid=uid,
        )
    except Exception:
        logger.exception("next-level generation failed", extra={"source_id": source.id})
        return None

    journey.difficulty = target_difficulty
    if not journey.tags:
        journey.tags = list(source.tags)

    record_usage(uid, in_tok, out_tok, get_config("journey")["model"], interaction_type="journey")
    _persist_journey(journey, uid)
    return journey
