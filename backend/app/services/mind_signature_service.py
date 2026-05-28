import hashlib
import json
from datetime import datetime, timezone

from app.core.database import get_db
from app.services.mastery_service import get_domain_mastery, update_domain_mastery
from app.services.provider_service import complete_text, get_config


LEGAL_DISCLAIMER = (
    "AI-generated capability indicator based on demonstrated learning engagement "
    "— not an accredited educational credential."
)

_NARRATIVE_SYSTEM_DEFAULT = """\
You are writing a capability narrative for a learner's Mind Signature — a verified record of their demonstrated intellectual range.

Write exactly 3 paragraphs. Be specific, warm, and grounded in the actual domains provided.
Do not use phrases like "the learner" or "the user". Use "you" to address them directly.
Do not make up capabilities beyond what the domain data suggests.
Do not add headers, bullet points, or markdown — just three flowing paragraphs separated by blank lines.

Paragraph 1: What domains they've explored and the intellectual range that reveals.
Paragraph 2: How their strongest domains connect or complement each other.
Paragraph 3: What this pattern suggests about how they think and learn.
"""


def _build_constellation(domains: list[dict], knowledge_nodes: list[dict]) -> dict:
    """Build constellation_data: nodes positioned in a circle, links from shared concept proximity."""
    import math

    nodes = []
    n = len(domains)
    for i, d in enumerate(domains):
        angle = (2 * math.pi * i / n) if n > 1 else 0
        radius = 160
        nodes.append({
            "id": d["domain"],
            "domain": d["domain"],
            "mastery": round(d["mastery_level"], 3),
            "concept_count": d["concept_count"],
            "x": round(200 + radius * math.cos(angle), 1),
            "y": round(200 + radius * math.sin(angle), 1),
        })

    # Links: pair every combination, weight = shared concept proximity (simplified: overlap score)
    domain_concepts: dict[str, set] = {}
    for kn in knowledge_nodes:
        domain_concepts.setdefault(kn["domain"], set()).add(kn["concept"])

    links = []
    domain_list = [d["domain"] for d in domains]
    for i in range(len(domain_list)):
        for j in range(i + 1, len(domain_list)):
            a, b = domain_list[i], domain_list[j]
            # Weight based on combined mastery — pure concept overlap rare across domains
            weight = round((domains[i]["mastery_level"] + domains[j]["mastery_level"]) / 2, 3)
            if weight > 0.15:
                links.append({"source": a, "target": b, "weight": weight})

    return {"nodes": nodes, "links": links}


async def generate_mind_signature(uid: str) -> dict:
    """Full pipeline: recalculate mastery → narrative → constellation → store → return."""
    update_domain_mastery(uid)
    domains = get_domain_mastery(uid)

    if not domains:
        raise ValueError("No domain mastery data available")

    # Fetch knowledge nodes for constellation building
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT concept, domain FROM knowledge_nodes WHERE uid = %s",
                (uid,),
            )
            knowledge_nodes = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT display_name FROM users WHERE uid = %s", (uid,))
            user_row = cur.fetchone()
            display_name = user_row["display_name"] if user_row else "Learner"

    domain_summary = "\n".join(
        f"- {d['domain']}: mastery {round(d['mastery_level'] * 100)}%, {d['concept_count']} concepts"
        for d in domains
    )

    cfg = get_config("mind_signature")
    narrative, _, _, _ = await complete_text(
        interaction_type="mind_signature",
        system=cfg["style_prompt"],
        user_content=(
            f"[SYSTEM CONTEXT — not part of conversation]\n"
            f"Learner name: {display_name}\n"
            f"Domain mastery data:\n{domain_summary}\n"
            f"[END SYSTEM CONTEXT]\n\n"
            f"Write their capability narrative."
        ),
        max_tokens=600,
    )

    constellation_data = _build_constellation(domains, knowledge_nodes)

    timestamp = datetime.now(timezone.utc).isoformat()
    sorted_domains = sorted(d["domain"] for d in domains)
    hash_input = f"{uid}:{':'.join(sorted_domains)}:{timestamp}"
    verification_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    domains_snapshot = json.dumps(domains, default=str)
    constellation_json = json.dumps(constellation_data)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mind_signatures
                  (uid, verification_hash, capability_narrative, domains, constellation_data)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING id, generated_at
                """,
                (uid, verification_hash, narrative, domains_snapshot, constellation_json),
            )
            row = cur.fetchone()

    return {
        "id": str(row["id"]),
        "uid": uid,
        "display_name": display_name,
        "verification_hash": verification_hash,
        "capability_narrative": narrative,
        "domains": domains,
        "constellation_data": constellation_data,
        "generated_at": row["generated_at"].isoformat(),
        "legal_disclaimer": LEGAL_DISCLAIMER,
    }


def get_latest_signature(uid: str) -> dict | None:
    """Return the most recent mind_signature for a user, or None."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ms.*, u.display_name
                FROM mind_signatures ms
                JOIN users u ON ms.uid = u.uid
                WHERE ms.uid = %s
                ORDER BY ms.generated_at DESC
                LIMIT 1
                """,
                (uid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["domains"] = d["domains"] if isinstance(d["domains"], list) else json.loads(d["domains"])
            d["constellation_data"] = d["constellation_data"] if isinstance(d["constellation_data"], dict) else json.loads(d["constellation_data"])
            d["id"] = str(d["id"])
            d["generated_at"] = d["generated_at"].isoformat() if hasattr(d["generated_at"], "isoformat") else d["generated_at"]
            d["legal_disclaimer"] = LEGAL_DISCLAIMER
            return d


def get_signature_by_hash(verification_hash: str) -> dict | None:
    """Public lookup by verification hash."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ms.*, u.display_name
                FROM mind_signatures ms
                JOIN users u ON ms.uid = u.uid
                WHERE ms.verification_hash = %s
                LIMIT 1
                """,
                (verification_hash,),
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["domains"] = d["domains"] if isinstance(d["domains"], list) else json.loads(d["domains"])
            d["constellation_data"] = d["constellation_data"] if isinstance(d["constellation_data"], dict) else json.loads(d["constellation_data"])
            d["id"] = str(d["id"])
            d["generated_at"] = d["generated_at"].isoformat() if hasattr(d["generated_at"], "isoformat") else d["generated_at"]
            # Don't expose uid in public endpoint
            d.pop("uid", None)
            d["legal_disclaimer"] = LEGAL_DISCLAIMER
            return d
