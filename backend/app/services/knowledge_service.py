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
