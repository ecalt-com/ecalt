"""
Cognitive fingerprint service.

Builds and stores a per-user cognitive fingerprint from conversation history.
The fingerprint is injected into AI system prompts to calibrate responses to
each learner's vocabulary level, abstraction preference, curiosity type, etc.

Update cadence: every 2nd message in a conversation (fire-and-forget background task).
Minimum confidence before injection: 0.3 (requires ~4–6 messages to reach).
"""
import json
import logging

from app.core.database import get_db
from app.services.provider_service import complete_text, get_config

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.3


def get_fingerprint(uid: str) -> dict | None:
    """Return the current fingerprint for a user, or None if not yet built or too sparse."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fingerprint, confidence FROM cognitive_fingerprints WHERE uid = %s",
                    (uid,),
                )
                row = cur.fetchone()
                if row and row["confidence"] >= _MIN_CONFIDENCE:
                    fp = row["fingerprint"]
                    return dict(fp) if isinstance(fp, dict) else json.loads(fp)
    except Exception as e:
        logger.debug("get_fingerprint failed uid=%s: %s", uid, e)
    return None


def build_fingerprint_block(fingerprint: dict) -> str:
    """
    Format a fingerprint dict into a concise system-prompt injection block.
    Returns empty string when fingerprint is None or confidence too low.
    """
    if not fingerprint:
        return ""
    if fingerprint.get("confidence", 0.0) < _MIN_CONFIDENCE:
        return ""

    voc      = fingerprint.get("vocabulary_complexity", 0.5)
    abs_pref = fingerprint.get("abstraction_preference", 0.5)
    narr     = fingerprint.get("narrative_score", 0.5)
    c_type   = fingerprint.get("curiosity_type", "conceptual")
    analogy  = fingerprint.get("analogy_preference", "none")
    velocity = fingerprint.get("engagement_velocity", "steady")
    persist  = fingerprint.get("concept_persistence", "explorer")

    lines = ["[LEARNER FINGERPRINT — calibrate every response to this]"]

    if voc >= 0.7:
        lines.append(f"vocabulary: {voc:.2f} → use technical vocabulary freely; no dumbing down")
    elif voc <= 0.3:
        lines.append(f"vocabulary: {voc:.2f} → clear everyday language; explain any jargon")
    else:
        lines.append(f"vocabulary: {voc:.2f} → balanced technical/everyday mix")

    if abs_pref >= 0.7:
        lines.append(f"abstraction: {abs_pref:.2f} → lead with the principle; example optional")
    elif abs_pref <= 0.3:
        lines.append(f"abstraction: {abs_pref:.2f} → ALWAYS anchor in a concrete example first")
    else:
        lines.append(f"abstraction: {abs_pref:.2f} → balance principle with example")

    if narr >= 0.65:
        lines.append(f"narrative: {narr:.2f} → lead with a scene, person, or moment; then the concept")
    elif narr <= 0.35:
        lines.append(f"narrative: {narr:.2f} → prefer direct claims and evidence; skip story framing")
    else:
        lines.append(f"narrative: {narr:.2f} → one analogy or story fragment per response if it sharpens the point")

    curiosity_map = {
        "factual":       "give precise, verifiable answers with specific numbers",
        "conceptual":    "go to first principles; explain the why beneath the what",
        "applied":       "always connect to real-world use or consequence",
        "philosophical": "explore implications, edge cases, and contradictions",
        "cross_domain":  "make unexpected connections to other fields freely",
    }
    lines.append(f"curiosity_type: {c_type} → {curiosity_map.get(c_type, 'follow their lead')}")

    analogy_map = {
        "mathematical": "use ratio, scale, and symmetry analogies",
        "biological":   "use organism, evolution, and ecosystem analogies",
        "mechanical":   "use gears, circuits, pressure, and flow analogies",
        "historical":   "use events, decisions, and people from history",
        "economic":     "use market, incentive, and cost-benefit analogies",
        "none":         "NEVER use analogies; use precise direct language only",
    }
    if analogy in analogy_map:
        lines.append(f"analogy_preference: {analogy} → {analogy_map[analogy]}")

    velocity_map = {
        "slow_build":  "open with familiar territory before going strange",
        "steady":      "consistent depth throughout",
        "fast_ignite": "skip basics; they reach for depth immediately",
    }
    lines.append(f"engagement_velocity: {velocity} → {velocity_map.get(velocity, 'match their pace')}")

    persist_map = {
        "explorer":   "transition earlier; never repeat already-covered ground",
        "returner":   "connect to concepts they explored in past sessions",
        "deep_diver": "stay deep; only advance when they show genuine mastery signals",
    }
    lines.append(f"concept_persistence: {persist} → {persist_map.get(persist, 'match their pattern')}")

    lines.append("[END FINGERPRINT]")
    return "\n".join(lines)


def inject_fingerprint(uid: str | None, base_system: str) -> str:
    """
    Fetch fingerprint for uid, build the block, and prepend it to base_system.
    Returns base_system unchanged if uid is None or fingerprint has insufficient confidence.
    """
    if not uid:
        return base_system
    fp = get_fingerprint(uid)
    if not fp:
        return base_system
    block = build_fingerprint_block(fp)
    if not block:
        return base_system
    return f"{block}\n\n{base_system}"


async def update_fingerprint(uid: str) -> None:
    """
    Background task: fetch the last 20 messages for this user, call the fingerprint
    AI, and upsert the result. Safe to call fire-and-forget — never raises.
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cm.role, cm.content
                    FROM conversation_messages cm
                    JOIN conversations c ON cm.conversation_id = c.id
                    WHERE c.uid = %s
                    ORDER BY cm.created_at DESC
                    LIMIT 20
                    """,
                    (uid,),
                )
                rows = cur.fetchall()
                messages = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

                cur.execute(
                    "SELECT fingerprint, message_count FROM cognitive_fingerprints WHERE uid = %s",
                    (uid,),
                )
                fp_row = cur.fetchone()
                existing_fp  = fp_row["fingerprint"] if fp_row else {}
                prior_count  = fp_row["message_count"] if fp_row else 0

        if not messages:
            return

        cfg = get_config("fingerprint")
        raw, _, _, _ = await complete_text(
            interaction_type="fingerprint",
            system=cfg["style_prompt"],
            user_content=(
                f"EXISTING FINGERPRINT:\n{json.dumps(existing_fp) if existing_fp else '{}'}\n\n"
                f"MESSAGES TO ANALYSE:\n{json.dumps(messages)}"
            ),
            max_tokens=600,
        )

        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("fingerprint AI returned no JSON for uid=%s", uid)
            return

        new_fp     = json.loads(raw[start:end])
        confidence = float(new_fp.get("confidence", 0.0))

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cognitive_fingerprints
                        (uid, fingerprint, message_count, confidence, updated_at)
                    VALUES (%s, %s::jsonb, %s, %s, now())
                    ON CONFLICT (uid) DO UPDATE SET
                        fingerprint   = EXCLUDED.fingerprint,
                        message_count = EXCLUDED.message_count,
                        confidence    = EXCLUDED.confidence,
                        updated_at    = now()
                    """,
                    (uid, json.dumps(new_fp), prior_count + len(messages), confidence),
                )
    except Exception as e:
        logger.warning("update_fingerprint failed uid=%s: %s", uid, e)
