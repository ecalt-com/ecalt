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


STEP_CONTENT_SYSTEM = """\
You are ECALT's expert educator. Write an engaging, practical lesson for a single learning step.

Return ONLY a valid JSON object with this exact structure:
{
  "content": "Full lesson text with simple markdown. Use **bold** for key terms. Use ## for section headings (max 4 words each). Use - for bullet lists. Target 400-550 words. Structure: hook paragraph → 2-3 key idea sections → a Try This activity → one key takeaway. Sound like a brilliant friend explaining over coffee, not a textbook. Be concrete, surprising, and immediately useful."
}

Rules:
- Never start with 'In this step' or 'Welcome to'
- Every section heading must start with a verb or noun (no 'Introduction', 'Overview')
- Make the Try This activity doable in 5 minutes without special equipment
- End with a single sentence takeaway in **bold**
"""


async def generate_step_content(
    step_title: str,
    step_description: str,
    step_type: str,
    journey_title: str,
    journey_question: str,
) -> str:
    client = get_client()
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=STEP_CONTENT_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Journey: {journey_title}\n"
                    f"Original question: {journey_question}\n"
                    f"Step title: {step_title}\n"
                    f"Step description: {step_description}\n"
                    f"Step type: {step_type}\n\n"
                    "Generate the lesson content JSON."
                ),
            }
        ],
    )
    raw = response.content[0].text.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("AI did not return valid content JSON")
    data = json.loads(raw[start:end])
    return data["content"]


async def warm_journey_steps(journey_id: str, steps: list[JourneyStep], journey_title: str, journey_question: str) -> None:
    """Background task: pre-generate and cache content for all steps in a journey."""
    from app.core.database import get_db
    for step in steps:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM step_content WHERE journey_id = %s AND step_id = %s",
                        (journey_id, step.id),
                    )
                    if cur.fetchone():
                        continue
            content = await generate_step_content(
                step_title=step.title,
                step_description=step.description,
                step_type=step.type,
                journey_title=journey_title,
                journey_question=journey_question,
            )
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO step_content (journey_id, step_id, content)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (journey_id, step_id) DO NOTHING
                        """,
                        (journey_id, step.id, content),
                    )
        except Exception:
            pass


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
