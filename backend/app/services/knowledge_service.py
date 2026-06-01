import json

from app.core.database import get_db
from app.services.provider_service import complete_text, get_config


_KNOWLEDGE_CONTRACT = """\
Return ONLY a valid JSON array — no markdown, no explanation, just the JSON.

[{"concept": "photosynthesis", "domain": "biology"}, ...]

Domain must be exactly one of: biology, physics, chemistry, math, history, technology, psychology, philosophy, arts, language, economics, engineering, astronomy, medicine"""

_VALID_DOMAINS = {
    "biology", "physics", "chemistry", "math", "history", "technology",
    "psychology", "philosophy", "arts", "language", "economics",
    "engineering", "astronomy", "medicine",
}

# Maps journey tags (and common synonyms) → canonical domain.
# Lowercase keys; values must all be members of _VALID_DOMAINS.
_TAG_DOMAIN_MAP: dict[str, str] = {
    # direct matches
    "biology": "biology", "physics": "physics", "chemistry": "chemistry",
    "math": "math", "history": "history", "technology": "technology",
    "psychology": "psychology", "philosophy": "philosophy", "arts": "arts",
    "language": "language", "economics": "economics", "engineering": "engineering",
    "astronomy": "astronomy", "medicine": "medicine",
    # biology adjacent
    "genetics": "biology", "molecules": "biology", "ecology": "biology",
    "evolution": "biology", "neuroscience": "medicine",
    # physics / engineering adjacent
    "acoustics": "physics", "quantum": "physics", "thermodynamics": "physics",
    "optics": "physics", "mechanics": "engineering", "electronics": "engineering",
    "rockets": "engineering", "space": "astronomy", "astrophysics": "astronomy",
    "cosmology": "astronomy",
    # technology / math adjacent
    "ai": "technology", "machine learning": "technology", "computing": "technology",
    "software": "technology", "programming": "technology",
    "statistics": "math", "algebra": "math", "calculus": "math",
    # economics adjacent
    "finance": "economics", "investing": "economics", "economy": "economics",
    # arts / language adjacent
    "music": "arts", "art": "arts", "creativity": "arts", "literature": "arts",
    "writing": "language", "linguistics": "language", "grammar": "language",
    # philosophy / psychology adjacent
    "logic": "philosophy", "ethics": "philosophy",
    "sociology": "psychology", "behavior": "psychology", "cognitive science": "psychology",
    # environment / climate → chemistry (atmospheric science)
    "climate": "chemistry", "environment": "biology",
}

# Strength credit per step type — reflects cognitive engagement depth.
# Chat extraction starts at 0.3; journey steps are intentionally lower
# (structured exposure) but accumulate across a full journey.
_STEP_TYPE_STRENGTH: dict[str, float] = {
    "concept":   0.15,   # reading / understanding
    "explore":   0.20,   # self-directed discovery
    "practice":  0.25,   # hands-on application
    "challenge": 0.30,   # active problem solving
}


def credit_step_knowledge(uid: str, step_title: str, step_type: str, tags: list[str]) -> None:
    """Upsert knowledge nodes when a journey step is freshly completed.

    Maps journey tags to canonical domains, then inserts/reinforces one
    knowledge node per domain using the step title as the concept name.
    Strength delta is weighted by step type so active steps count more.
    Silently no-ops if no valid domain can be resolved from the tags.
    """
    domains: list[str] = list({
        mapped
        for tag in tags
        if (mapped := _TAG_DOMAIN_MAP.get(tag.strip().lower())) and mapped in _VALID_DOMAINS
    })
    if not domains:
        return

    concept = step_title.strip()[:100]
    delta = _STEP_TYPE_STRENGTH.get(step_type, 0.15)

    with get_db() as conn:
        with conn.cursor() as cur:
            for domain in domains:
                cur.execute(
                    """
                    INSERT INTO knowledge_nodes (uid, concept, domain, strength)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (uid, concept) DO UPDATE SET
                        strength        = LEAST(knowledge_nodes.strength + %s, 1.0),
                        last_reinforced = now()
                    """,
                    (uid, concept, domain, delta, delta),
                )


async def extract_knowledge_nodes(uid: str, user_message: str, assistant_response: str) -> None:
    """Extract concept-domain pairs from a conversation turn and upsert into knowledge_nodes."""
    excerpt = f"Learner: {user_message[:300]}\nResponse: {assistant_response[:400]}"

    cfg = get_config("knowledge_extraction")
    system = f"{cfg['style_prompt']}\n\n{_KNOWLEDGE_CONTRACT}"
    raw, _, _, _ = await complete_text(
        interaction_type="knowledge_extraction",
        system=system,
        user_content=f"[CONVERSATION]:\n{excerpt}",
        max_tokens=300,
    )
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return

    try:
        nodes = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return

    if not nodes:
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            for node in nodes[:8]:
                concept = str(node.get("concept", "")).strip()[:100]
                domain = str(node.get("domain", "")).strip().lower()
                if not concept or domain not in _VALID_DOMAINS:
                    continue
                cur.execute(
                    """
                    INSERT INTO knowledge_nodes (uid, concept, domain, strength)
                    VALUES (%s, %s, %s, 0.3)
                    ON CONFLICT (uid, concept) DO UPDATE SET
                        strength        = LEAST(knowledge_nodes.strength + 0.15, 1.0),
                        last_reinforced = now()
                    """,
                    (uid, concept, domain),
                )


async def get_nodes_for_user(uid: str) -> list[dict]:
    """Return knowledge nodes ordered by strength descending."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT concept, domain, strength, discovered_at, last_reinforced
                FROM knowledge_nodes WHERE uid = %s
                ORDER BY strength DESC, last_reinforced DESC
                LIMIT 60
                """,
                (uid,),
            )
            return [dict(r) for r in cur.fetchall()]
