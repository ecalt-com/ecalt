import json
import uuid
from datetime import datetime, timezone

from app.models.schemas import Journey, JourneyStep
from app.services.fingerprint_service import inject_fingerprint
from app.services.provider_service import complete_text, get_config


_JOURNEY_CONTRACT = """\
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
}"""


_STEP_CONTENT_CONTRACT = """\
Return ONLY a valid JSON object with this exact structure:
{
  "content": "..."
}

The content field must follow this exact structure (use \\n\\n between each block):

1. Opening hook — 2-3 sentences. Start with a wow fact, a question, or a mini story. Use **bold** for the most surprising word or phrase. Add 1 relevant emoji at the very start.

2. ## [Section heading with emoji] — 3-5 bullet points using - prefix. Each bullet: one crisp sentence. Bold key terms. Keep it playful and clear.

3. ## [Section heading with emoji] — another 3-5 bullets. Different angle on the topic.

4. (Optional) ## [Third section if needed]

5. ## 🎯 Try This! — A fun hands-on activity doable in 5 minutes, no special equipment. Write it as excited steps. Bold the action verbs.

6. Final paragraph — One-sentence takeaway in **bold**, capturing the biggest idea."""


async def generate_step_content(
    step_title: str,
    step_description: str,
    step_type: str,
    journey_title: str,
    journey_question: str,
    age_group: str = "all",
    uid: str | None = None,
) -> tuple[str, int, int]:
    """Returns (content, estimated_input_tokens, estimated_output_tokens)."""
    user_content = (
        f"Journey: {journey_title}\n"
        f"Original question: {journey_question}\n"
        f"Step title: {step_title}\n"
        f"Step description: {step_description}\n"
        f"Step type: {step_type}\n"
        f"Age group: {age_group}\n\n"
        "Generate the lesson content JSON."
    )
    cfg = get_config("step_content")
    system = f"{inject_fingerprint(uid, cfg['style_prompt'])}\n\n{_STEP_CONTENT_CONTRACT}"
    raw, in_tok, out_tok, _ = await complete_text(
        interaction_type="step_content",
        system=system,
        user_content=user_content,
        max_tokens=1500,
    )
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("AI did not return valid content JSON")
    data = json.loads(raw[start:end])
    content = data["content"]
    return content, in_tok, out_tok


async def warm_journey_steps(
    journey_id: str,
    steps: list[JourneyStep],
    journey_title: str,
    journey_question: str,
    age_group: str = "all",
    uid: str | None = None,
) -> None:
    """Background task: pre-generate and cache content for all steps in a journey."""
    from app.core.database import get_db
    from app.services.subscription_service import record_usage
    from app.services.provider_service import get_config
    model = get_config("step_content")["model"]

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
            content, in_tok, out_tok = await generate_step_content(
                step_title=step.title,
                step_description=step.description,
                step_type=step.type,
                journey_title=journey_title,
                journey_question=journey_question,
                age_group=age_group,
                uid=uid,
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
            if uid:
                record_usage(uid, in_tok, out_tok, model, interaction_type="step_content")
        except Exception:
            pass


async def generate_journey(question: str, age_group: str = "all", uid: str | None = None) -> tuple[Journey, int, int]:
    """Returns (journey, estimated_input_tokens, estimated_output_tokens)."""
    user_content = f"Question: {question}\nTarget age group: {age_group}\n\nGenerate the learning journey JSON."
    cfg = get_config("journey")
    system = f"{inject_fingerprint(uid, cfg['style_prompt'])}\n\n{_JOURNEY_CONTRACT}"
    raw, in_tok, out_tok, _ = await complete_text(
        interaction_type="journey",
        system=system,
        user_content=user_content,
        max_tokens=2048,
    )

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

    journey = Journey(
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
    return journey, in_tok, out_tok
