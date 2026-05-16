import json
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import anthropic

from app.core.config import settings
from app.models.schemas import Mission, MissionStep

# ── Lazy client ──────────────────────────────────────────────────────────────

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


# ── In-memory rate limiter ────────────────────────────────────────────────────

FREE_SPARK_LIMIT = 5
WINDOW_MINUTES = 60

_lock = threading.Lock()
_sessions: dict[str, dict] = defaultdict(lambda: {"count": 0, "expires_at": None})


def consume_spark(session_id: str) -> tuple[bool, int, int]:
    """Return (allowed, sparks_used, sparks_remaining)."""
    now = datetime.now(timezone.utc)
    with _lock:
        s = _sessions[session_id]
        if s["expires_at"] is None or now > s["expires_at"]:
            s["count"] = 0
            s["expires_at"] = now + timedelta(minutes=WINDOW_MINUTES)
        if s["count"] >= FREE_SPARK_LIMIT:
            return False, s["count"], 0
        s["count"] += 1
        remaining = FREE_SPARK_LIMIT - s["count"]
        return True, s["count"], remaining


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are ECALT's curiosity engine. Give a SHORT vivid answer then propose a learning mission.

Return ONLY valid JSON — no markdown, no extra text:
{
  "answer": "2-3 sentences. Start with a surprising fact or analogy. NOT textbook tone.",
  "mission": {
    "title": "Mission title (max 7 words)",
    "tagline": "One sentence that makes the learner itch to start",
    "category": "biology|physics|math|tech|history|arts|finance|language|engineering|psychology",
    "difficulty": "beginner|intermediate|advanced",
    "estimated_minutes": 30,
    "icon": "single emoji that represents this topic",
    "steps": [
      {"title": "Step title (action-oriented)", "type": "concept|practice|challenge|explore", "minutes": 10}
    ]
  }
}

Rules:
- Answer: 2-3 sentences ONLY. Be vivid and concrete — surprise them.
- Mission: exactly 4-5 steps that build naturally from the question.
- Step titles must be action-oriented ("Build your first...", "Decode the...", not "Learn about...").
- estimated_minutes must equal the sum of all step minutes.
"""


# ── Generator ─────────────────────────────────────────────────────────────────

async def generate_spark(question: str) -> tuple[str, Mission]:
    response = await _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"Question: {question}"}],
    )

    raw = response.content[0].text.strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("AI returned an unexpected response format")

    data = json.loads(raw[start:end])
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
