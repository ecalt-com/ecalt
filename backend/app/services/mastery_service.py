from app.core.database import get_db


def update_domain_mastery(uid: str) -> None:
    """Recalculate domain_mastery from knowledge_nodes grouped by domain."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Get per-domain aggregates from knowledge_nodes
            cur.execute(
                """
                SELECT
                    domain,
                    COUNT(*) AS concept_count,
                    AVG(strength) AS avg_strength,
                    COUNT(*) FILTER (WHERE last_reinforced >= now() - interval '30 days') AS recent_count
                FROM knowledge_nodes
                WHERE uid = %s
                GROUP BY domain
                """,
                (uid,),
            )
            rows = cur.fetchall()
            for row in rows:
                domain = row["domain"]
                concept_count = row["concept_count"]
                avg_strength = float(row["avg_strength"] or 0)
                recent_count = row["recent_count"]

                # mastery_level: weighted combo of concept breadth + average strength
                breadth_score = min(concept_count / 15.0, 1.0)
                mastery_level = round((breadth_score * 0.5 + avg_strength * 0.5), 4)

                # learning_velocity: concepts touched in last 30 days / 30
                learning_velocity = round(recent_count / 30.0, 4)

                cur.execute(
                    """
                    INSERT INTO domain_mastery (uid, domain, mastery_level, concept_count, learning_velocity)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (uid, domain) DO UPDATE SET
                        mastery_level    = EXCLUDED.mastery_level,
                        concept_count    = EXCLUDED.concept_count,
                        learning_velocity = EXCLUDED.learning_velocity,
                        updated_at       = now()
                    """,
                    (uid, domain, mastery_level, concept_count, learning_velocity),
                )


def get_domain_mastery(uid: str) -> list[dict]:
    """Return all domain_mastery rows for a user, ordered by mastery desc."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain, mastery_level, concept_count, learning_velocity, updated_at
                FROM domain_mastery
                WHERE uid = %s
                ORDER BY mastery_level DESC
                """,
                (uid,),
            )
            return [dict(r) for r in cur.fetchall()]


def detect_mastery_boundaries(uid: str) -> list[str]:
    """Return list of domain names that have crossed the mastery boundary."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain FROM domain_mastery
                WHERE uid = %s AND mastery_level >= 0.5 AND concept_count >= 4
                ORDER BY mastery_level DESC
                """,
                (uid,),
            )
            return [r["domain"] for r in cur.fetchall()]


def should_generate_signature(uid: str) -> bool:
    """True if mastery boundaries exist and no signature generated in the last 7 days."""
    qualifying = detect_mastery_boundaries(uid)
    if not qualifying:
        return False

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM mind_signatures
                WHERE uid = %s AND generated_at >= now() - interval '7 days'
                """,
                (uid,),
            )
            return cur.fetchone()["n"] == 0
