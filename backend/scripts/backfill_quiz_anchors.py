"""
Backfill quiz_anchors for existing step_content rows that have content but
no anchors yet. Runs once as a background script — not on the hot path.

Usage:
  python scripts/backfill_quiz_anchors.py [--limit N] [--dry-run]
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_db
from app.services.provider_service import complete_text

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = """\
You are an educational content analyst. Extract quiz-testable facts from the
given step content.

Each fact must be:
(a) Explicitly stated in the content — not implied or inferred
(b) Falsifiable: there is a clearly wrong answer possible
(c) Different from the other facts — no two facts test the same idea

Do NOT extract vague statements:
BAD:  "Encryption is important for security"
GOOD: "AES-256 encryption would take longer than the age of the universe to brute-force"

testable_as values:
  application → "If X, what happens to Y?"
  implication → "Given X, what does this mean for Z?"
  exception   → "Under what conditions does X break down?"
  connection  → "How does X relate to [another concept in this content]?"

Return ONLY a valid JSON array of 3–5 objects:
[
  {
    "fact": "One sentence stating something explicitly in the content",
    "testable_as": "application | implication | exception | connection",
    "hint_direction": "One phrase pointing toward the answer without stating it"
  }
]"""


async def _extract_anchors(content: str) -> list[dict]:
    user_msg = f"Step content:\n---\n{content[:4000]}\n---\n\nExtract 3–5 quiz-testable facts."
    try:
        raw, _, _, _ = await complete_text(
            interaction_type="step_content",
            system=_EXTRACT_SYSTEM,
            user_content=user_msg,
            max_tokens=600,
        )
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start != -1 and end > start:
            anchors = json.loads(raw[start:end])
            if isinstance(anchors, list):
                return anchors
    except Exception as e:
        logger.warning("anchor extraction failed: %s", e)
    return []


def _get_unanchored_rows(limit: int) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, journey_id, step_id, content
                FROM step_content
                WHERE (quiz_anchors IS NULL OR quiz_anchors = '[]'::jsonb)
                  AND content IS NOT NULL AND length(content) > 100
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]


def _store_anchors(row_id: str, anchors: list[dict]) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE step_content SET quiz_anchors = %s::jsonb WHERE id = %s",
                (json.dumps(anchors), row_id),
            )


async def run_backfill(limit: int = 500, dry_run: bool = False) -> None:
    rows = _get_unanchored_rows(limit)
    logger.info("Found %d rows to backfill", len(rows))

    for i, row in enumerate(rows, 1):
        logger.info("[%d/%d] %s/%s", i, len(rows), row["journey_id"][:8], row["step_id"][:8])
        anchors = await _extract_anchors(row["content"])
        if not anchors:
            logger.warning("  no anchors extracted — skipping")
            continue
        logger.info("  extracted %d anchors", len(anchors))
        if not dry_run:
            _store_anchors(row["id"], anchors)

    logger.info("Backfill complete (%s).", "dry run" if dry_run else "committed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill quiz_anchors for existing step content")
    parser.add_argument("--limit",   type=int, default=500, help="Max rows to process")
    parser.add_argument("--dry-run", action="store_true",   help="Extract but do not write to DB")
    args = parser.parse_args()

    asyncio.run(run_backfill(limit=args.limit, dry_run=args.dry_run))
