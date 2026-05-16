import json
import uuid
from datetime import datetime, timezone

import anthropic

from app.core.config import settings
from app.models.schemas import Journey, JourneyStep

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """\
You are ECALT's AI learning designer. Your job is to transform any question into an \
engaging, structured learning journey.

Return ONLY a valid JSON object — no markdown, no explanation — with this exact structure:
{
  "title": "Compelling journey title",
  "description": "1-2 sentence hook that makes the learner excited to start",
  "age_group": "kids | teens | adults | all",
  "difficulty": "beginner | intermediate | advanced",
  "estimated_hours": 2.5,
  "icon": "single emoji representing this topic",
  "tags": ["tag1", "tag2", "tag3"],
  "steps": [
    {
      "title": "Step title",
      "description": "What the learner will discover — vivid, curious, not textbook",
      "type": "concept | practice | challenge | explore",
      "estimated_minutes": 15
    }
  ]
}

Rules:
- 6 to 12 steps that build progressively
- Step types: concept (learn the idea), practice (do it), challenge (test yourself), explore (go deeper)
- Make it feel like exploration, not a curriculum
- Adapt complexity to the learner's likely age and level
- Keep descriptions under 120 characters each
- Estimated hours should reflect the sum of step minutes
"""


async def generate_journey(question: str, age_group: str = "all") -> Journey:
    client = get_client()

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\nTarget age group: {age_group}\n\nGenerate the learning journey JSON.",
            }
        ],
    )

    raw = response.content[0].text.strip()

    # Extract JSON robustly
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("AI did not return valid JSON")

    data = json.loads(raw[start:end])

    steps = [
        JourneyStep(
            id=str(uuid.uuid4()),
            title=step["title"],
            description=step["description"],
            type=step["type"],
            estimated_minutes=int(step["estimated_minutes"]),
        )
        for step in data["steps"]
    ]

    return Journey(
        id=str(uuid.uuid4()),
        question=question,
        title=data["title"],
        description=data["description"],
        age_group=data.get("age_group", "all"),
        difficulty=data.get("difficulty", "beginner"),
        estimated_hours=float(data["estimated_hours"]),
        steps=steps,
        tags=data.get("tags", []),
        icon=data.get("icon", "📚"),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
