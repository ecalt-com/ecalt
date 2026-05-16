import json
import uuid
from datetime import datetime, timedelta, timezone

import anthropic

from app.core.config import settings
from app.core.supabase import get_supabase
from app.models.schemas import Mission, MissionStep

# ── Lazy client ───────────────────────────────────────────────────────────────

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── DB-backed spark store ─────────────────────────────────────────────────────

FREE_SPARK_LIMIT = 5
WINDOW_MINUTES = 60


def consume_spark(key: str) -> tuple[bool, int, int]:
    """
    Attempt to consume one spark for the given key (uid or session_id).
    Returns (allowed, sparks_used, sparks_remaining).
    Backed by Supabase — survives redeploys.
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)

    result = db.table("spark_usage").select("*").eq("key", key).execute()
    row = result.data[0] if result.data else None

    if row is None or row["expires_at"] is None or now > datetime.fromisoformat(row["expires_at"]):
        # Fresh window
        expires_at = (now + timedelta(minutes=WINDOW_MINUTES)).isoformat()
        db.table("spark_usage").upsert(
            {"key": key, "count": 1, "expires_at": expires_at}, on_conflict="key"
        ).execute()
        return True, 1, FREE_SPARK_LIMIT - 1

    count = row["count"]
    if count >= FREE_SPARK_LIMIT:
        return False, count, 0

    new_count = count + 1
    db.table("spark_usage").update({"count": new_count}).eq("key", key).execute()
    return True, new_count, FREE_SPARK_LIMIT - new_count


def get_session_status(key: str) -> tuple[int, int]:
    """
    Read spark count without consuming one.
    Returns (sparks_used, sparks_remaining).
    """
    db = get_supabase()
    now = datetime.now(timezone.utc)

    result = db.table("spark_usage").select("*").eq("key", key).execute()
    row = result.data[0] if result.data else None

    if row is None or row["expires_at"] is None or now > datetime.fromisoformat(row["expires_at"]):
        return 0, FREE_SPARK_LIMIT

    used = min(row["count"], FREE_SPARK_LIMIT)
    return used, max(0, FREE_SPARK_LIMIT - used)


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are ECALT's curiosity engine. Your job: give a SHORT vivid answer, then propose a mission.

Return ONLY a valid JSON object. No markdown, no explanation, no extra text — just the JSON.

{
  "answer": "EXACTLY 2-3 sentences. Under 120 words. Open with a concrete fact, number, or analogy that surprises the learner. Never start with 'I' or 'Sure'. Sound like a curious friend, not a textbook.",
  "mission": {
    "title": "Action-packed mission title (max 7 words)",
    "tagline": "One sentence that makes the learner itch to start — what they'll be able to DO",
    "category": "one of: biology|physics|math|tech|history|arts|finance|language|engineering|psychology",
    "difficulty": "one of: beginner|intermediate|advanced",
    "estimated_minutes": 30,
    "icon": "single emoji representing the topic",
    "steps": [
      {"title": "Step title — start with a verb (Build, Decode, Wire, Map...)", "type": "concept|practice|challenge|explore", "minutes": 10}
    ]
  }
}

Strict rules:
- answer: 2-3 sentences, ≤ 120 words. Vivid, concrete, surprising. No filler phrases.
- mission.steps: exactly 4-5 steps that progress logically from the question.
- estimated_minutes must equal the exact sum of all step minutes.
- Every step title must start with an action verb.
"""


# ── Generator ─────────────────────────────────────────────────────────────────

async def generate_spark(question: str) -> tuple[str, Mission]:
    response = await _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=750,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"Question: {question}"}],
    )

    raw = response.content[0].text.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("AI returned an unexpected response format")

    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {e}")

    m = data["mission"]
    steps = [
        MissionStep(title=s["title"], type=s["type"], minutes=int(s["minutes"]))
        for s in m["steps"]
    ]
    mission = Mission(
        id=str(uuid.uuid4()),
        title=m["title"],
        tagline=m["tagline"],
        category=m["category"],
        difficulty=m["difficulty"],
        estimated_minutes=int(m["estimated_minutes"]),
        icon=m["icon"],
        steps=steps,
    )
    return data["answer"], mission
