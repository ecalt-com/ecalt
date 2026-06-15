"""
Builds a ranked interest profile for a user from all available signals:
  - journeys.question / tags  (every /explore call is a search log)
  - domain_mastery             (mastery level + velocity per domain)
  - quiz_results               (concepts where the user struggles)
  - user_interests.topics      (declared at onboarding)
  - knowledge_nodes.strength   (concept-level granularity)

Pure read — no AI, no writes. Cached in-process for 1 hour per uid.
"""
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_db

logger = logging.getLogger(__name__)

# ── In-process cache ──────────────────────────────────────────────────────────

_CACHE_TTL_SECONDS = 3600

_cache: dict[str, tuple["InterestProfile", float]] = {}  # uid → (profile, computed_at epoch)


def invalidate(uid: str) -> None:
    """Drop the cached profile for a user (call after explore or journey completion)."""
    _cache.pop(uid, None)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TopicSignal:
    topic: str
    weight: float           # 0.0–1.0 after normalisation
    signal_type: str        # "interest" | "mastery_gap" | "level_up" | "quiz_struggle" | "declared"


@dataclass
class InterestProfile:
    uid: str
    top_topics: list[TopicSignal] = field(default_factory=list)
    preferred_difficulty: str = "beginner"
    age_group: str = "all"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Helpers ───────────────────────────────────────────────────────────────────

_DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced"]


def _decay(days: float, half_life: float = 14.0) -> float:
    """Exponential decay so recent signals outweigh old ones."""
    return math.exp(-days * math.log(2) / half_life)


def _days_ago(ts) -> float:
    if ts is None:
        return 30.0
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return 30.0
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 86400)


def _normalise(raw: dict[str, float]) -> dict[str, float]:
    if not raw:
        return {}
    mx = max(raw.values())
    if mx == 0:
        return raw
    return {k: v / mx for k, v in raw.items()}


def _extract_noun_tokens(text: str) -> list[str]:
    """Very cheap noun-ish token extraction — good enough for interest signals."""
    tokens = re.findall(r"[a-z]{4,}", text.lower())
    stopwords = {
        "does", "work", "what", "how", "why", "when", "that", "this", "with",
        "from", "have", "will", "they", "been", "were", "your", "their", "about",
        "which", "make", "made", "into", "through",
    }
    return [t for t in tokens if t not in stopwords]


# ── Main builder ──────────────────────────────────────────────────────────────

def _build_profile(uid: str) -> InterestProfile:
    raw: dict[str, float] = {}
    signal_types: dict[str, str] = {}
    age_group = "all"
    difficulty_counts: dict[str, int] = {"beginner": 0, "intermediate": 0, "advanced": 0}

    # ── 1. Explore search history (journeys table) ────────────────────────────
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT question, tags, difficulty, created_at
                    FROM journeys
                    WHERE uid = %s AND is_curated = FALSE
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (uid,),
                )
                for r in cur.fetchall():
                    days = _days_ago(r["created_at"])
                    weight = _decay(days) * 1.0  # base weight for explore signal

                    # Tags directly
                    for tag in (r["tags"] or []):
                        t = tag.strip().lower()
                        if t:
                            raw[t] = raw.get(t, 0.0) + weight
                            signal_types.setdefault(t, "interest")

                    # Noun tokens from the raw question
                    for tok in _extract_noun_tokens(r["question"] or ""):
                        raw[tok] = raw.get(tok, 0.0) + weight * 0.5
                        signal_types.setdefault(tok, "interest")

                    # Count difficulties to infer preferred level
                    diff = r.get("difficulty") or "beginner"
                    if diff in difficulty_counts:
                        difficulty_counts[diff] += 1
    except Exception:
        logger.exception("interest_profile: failed to load journeys")

    # ── 2. Declared interests (onboarding) ───────────────────────────────────
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT topics, age_group FROM user_interests WHERE uid = %s",
                    (uid,),
                )
                row = cur.fetchone()
                if row:
                    age_group = row.get("age_group") or "all"
                    for topic in (row["topics"] or []):
                        t = topic.strip().lower()
                        if t:
                            raw[t] = raw.get(t, 0.0) + 0.5
                            signal_types.setdefault(t, "declared")
    except Exception:
        logger.exception("interest_profile: failed to load user_interests")

    # ── 3. Domain mastery ─────────────────────────────────────────────────────
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT domain, mastery_level, learning_velocity, updated_at FROM domain_mastery WHERE uid = %s",
                    (uid,),
                )
                for r in cur.fetchall():
                    domain = (r["domain"] or "").strip().lower()
                    if not domain:
                        continue
                    mastery = float(r["mastery_level"] or 0.0)
                    days = _days_ago(r["updated_at"])

                    if mastery < 0.4:
                        # Gap — user touched this domain but hasn't mastered it
                        w = 0.8 * _decay(days, half_life=21)
                        signal_types[domain] = "mastery_gap"
                    elif mastery > 0.7:
                        # High mastery → ready to level up
                        w = 0.6 * _decay(days, half_life=30)
                        signal_types.setdefault(domain, "level_up")
                    else:
                        w = 0.4 * _decay(days, half_life=21)
                        signal_types.setdefault(domain, "interest")

                    raw[domain] = raw.get(domain, 0.0) + w

                    # Track difficulty for preferred level inference
                    if mastery > 0.7:
                        difficulty_counts["intermediate"] += 1  # push toward next
    except Exception:
        logger.exception("interest_profile: failed to load domain_mastery")

    # ── 4. Quiz struggles ─────────────────────────────────────────────────────
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT concept,
                           SUM(CASE WHEN is_correct THEN 0 ELSE 1 END)::float /
                               NULLIF(COUNT(*), 0) AS fail_rate,
                           MAX(answered_at) AS last_answered
                    FROM quiz_results
                    WHERE uid = %s
                      AND answered_at > NOW() - INTERVAL '30 days'
                    GROUP BY concept
                    HAVING COUNT(*) >= 2
                    """,
                    (uid,),
                )
                for r in cur.fetchall():
                    fail_rate = float(r["fail_rate"] or 0.0)
                    if fail_rate < 0.5:
                        continue
                    concept = (r["concept"] or "").strip().lower()
                    if not concept:
                        continue
                    days = _days_ago(r["last_answered"])
                    w = 0.9 * fail_rate * _decay(days, half_life=7)
                    raw[concept] = raw.get(concept, 0.0) + w
                    signal_types[concept] = "quiz_struggle"
    except Exception:
        logger.exception("interest_profile: failed to load quiz_results")

    # ── 5. Knowledge nodes (low-strength concepts in visited domains) ─────────
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT domain, AVG(strength) AS avg_strength, MAX(last_reinforced) AS last_seen
                    FROM knowledge_nodes
                    WHERE uid = %s
                    GROUP BY domain
                    """,
                    (uid,),
                )
                for r in cur.fetchall():
                    domain = (r["domain"] or "").strip().lower()
                    if not domain:
                        continue
                    avg_str = float(r["avg_strength"] or 0.5)
                    if avg_str < 0.5:
                        days = _days_ago(r["last_seen"])
                        w = 0.4 * (1 - avg_str) * _decay(days, half_life=21)
                        raw[domain] = raw.get(domain, 0.0) + w
                        signal_types.setdefault(domain, "mastery_gap")
    except Exception:
        logger.exception("interest_profile: failed to load knowledge_nodes")

    # ── Preferred difficulty ───────────────────────────────────────────────────
    # If user has explored 3+ beginner journeys → prefer intermediate, etc.
    preferred_difficulty = "beginner"
    for diff in ["advanced", "intermediate", "beginner"]:
        if difficulty_counts.get(diff, 0) >= 3:
            idx = _DIFFICULTY_ORDER.index(diff)
            next_idx = min(idx + 1, len(_DIFFICULTY_ORDER) - 1)
            preferred_difficulty = _DIFFICULTY_ORDER[next_idx]
            break

    # ── Assemble top_topics ───────────────────────────────────────────────────
    normalised = _normalise(raw)
    top_topics = [
        TopicSignal(topic=k, weight=v, signal_type=signal_types.get(k, "interest"))
        for k, v in sorted(normalised.items(), key=lambda x: -x[1])
        if v >= 0.05
    ][:10]

    return InterestProfile(
        uid=uid,
        top_topics=top_topics,
        preferred_difficulty=preferred_difficulty,
        age_group=age_group,
    )


async def get_interest_profile(uid: str) -> InterestProfile:
    """Return the user's ranked interest profile, cached for 1 hour."""
    import time
    cached = _cache.get(uid)
    if cached:
        profile, computed_at = cached
        if time.time() - computed_at < _CACHE_TTL_SECONDS:
            return profile

    profile = _build_profile(uid)
    _cache[uid] = (profile, time.time())
    return profile
