"""Generates notification copy using the nudge AI interaction type (Claude Haiku by default)."""
import json
import logging

from app.services.provider_service import complete_text

logger = logging.getLogger("app.services.copy_generator")

_SYSTEM = """\
You are the voice of ECALT — an AI-powered curiosity learning platform.
Write a notification message that feels like it's coming from a brilliant friend, not a marketing bot.

Rules:
- Address the user by their first name naturally — not robotically
- WhatsApp short_message must feel conversational, warm, under 130 chars — a link will be appended automatically
- Put the actual insight or hook IN the message body, not just "click here to find out"
- Email body_html: 2-3 short paragraphs + a single clear CTA button at the end
- No exclamation mark overload, no corporate language, no clickbait
- Make it feel like the platform genuinely noticed something specific about their learning

Return a JSON object with exactly these keys:
  subject       — email subject line (max 60 chars)
  body_html     — HTML email body with CTA button
  short_message — WhatsApp plain text (max 130 chars, conversational, starts with their first name, NO URL)

Return ONLY the raw JSON. No markdown fences. No explanation."""

_TEMPLATES: dict[str, str] = {
    "daily_spark": (
        "User's name: {name}. Recent topics: {topics}. Today's angle: {angle}. "
        "Send a personalised daily curiosity nudge that connects to what they've been exploring. "
        "Make the short_message feel like a fascinating question from a smart friend."
    ),
    "re_engagement": (
        "User's name: {name}. Inactive for {days_inactive} days. Favourite domain: {domain}. "
        "Write a warm, non-pushy message that sparks curiosity about {domain} — "
        "give them one specific surprising fact or question about it right in the message body. "
        "Don't say 'we miss you', just make them curious."
    ),
    "cliffhanger_return": (
        "User's name: {name}. They left a learning conversation about '{topic}' without resolving it. "
        "Reference the specific topic and tease the unresolved angle — "
        "make them feel like they'd genuinely regret not finding the answer. "
        "The short_message should feel like a friend texting: 'hey wait, did you ever figure out why...?'"
    ),
    "connection_alert": (
        "User's name: {name}. Their topics '{topic_a}' and '{topic_b}' share a surprising connection: {connection}. "
        "Deliver this cross-domain insight in a way that makes them go 'wait, really?' "
        "Lead with the surprising fact."
    ),
    "milestone_approach": (
        "User's name: {name}. Only {steps_remaining} step(s) away from completing their '{journey_title}' journey. "
        "Motivate them to finish — make the finish line feel close and achievable. "
        "Be specific about the journey."
    ),
    "mind_signature_ready": (
        "User's name: {name}. They've earned a new Mind Signature in {domain}. "
        "Celebrate the achievement genuinely — explain what a Mind Signature means "
        "and invite them to see their personalised knowledge constellation."
    ),
    "mind_signature_nudge": (
        "User's name: {name}. They are {mastery_pct}% of the way to earning a Mind Signature in {domain}. "
        "Tease what a Mind Signature is (a personalised constellation of their intellectual range) "
        "and show them how close they are. Make it feel worth pushing for."
    ),
    "world_event_hook": (
        "User's name: {name}. A real-world event ({event}) connects to their learning topic '{topic}'. "
        "Show them exactly why this matters to what they've been studying — be specific."
    ),
    "streak_at_risk": (
        "User's name: {name}. They have a {streak_days}-day learning streak that will break tonight "
        "if they don't do one session. Write an urgent but warm nudge — "
        "not scary, just a friendly 'hey, don't let this slip'. "
        "Make it feel low-effort: '5 minutes is enough'."
    ),
    "streak_lost": (
        "User's name: {name}. They just lost their {streak_days}-day learning streak. "
        "Write a compassionate, forward-looking message. Acknowledge the loss briefly but focus on "
        "starting fresh — make day 1 feel exciting, not like punishment. "
        "No guilt-tripping."
    ),
    "streak_milestone": (
        "User's name: {name}. They just hit a {streak_days}-day learning streak milestone. "
        "Celebrate it warmly and specifically — make them feel like this is a real achievement "
        "worth being proud of. Be enthusiastic but not over-the-top."
    ),
    "journey_almost_done": (
        "User's name: {name}. They are {steps_remaining} step(s) away from finishing "
        "their '{journey_title}' journey. "
        "Motivate them across the finish line — most people who get this close never finish. "
        "Make completing it feel meaningful and easy."
    ),
    "weekly_digest": (
        "User's name: {name}. This week they explored {new_concepts} new concepts across "
        "{active_domains} domains ({domains}), and touched {journeys_touched} learning journey(s). "
        "Write a warm, celebratory weekly summary that makes them feel like they've genuinely "
        "built something. Reference the specific domains they explored."
    ),
    "family_highlight": (
        "User's name: {name}. Weekly family learning summary: {summary}. "
        "Write a warm summary that celebrates the family's curiosity this week."
    ),
}

_FALLBACK = {
    "subject": "Something interesting for you",
    "body_html": "<p>Come explore something new today on <strong>ECALT</strong>.</p>",
    "short_message": "Hey! Something new is waiting for you on ECALT. Come take a look.",
}


def _first_name(name: str) -> str:
    return (name or "").strip().split()[0] if name else "there"


async def generate_copy(notification_type: str, context: dict) -> dict:
    raw_name = context.get("name") or context.get("display_name") or ""
    first = _first_name(raw_name)
    ctx = {**context, "name": first}

    system = _SYSTEM

    template = _TEMPLATES.get(
        notification_type,
        "User's name: {name}. Generate a {type} notification using this context: {context}.",
    )
    try:
        user_prompt = template.format(type=notification_type, context=json.dumps(ctx), **ctx)
    except (KeyError, ValueError):
        user_prompt = f"User's name: {first}. Generate a {notification_type} notification. Context: {json.dumps(ctx)}"

    try:
        raw, _, _, _ = await complete_text(
            interaction_type="nudge",
            system=system,
            user_content=user_prompt,
            max_tokens=512,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```", 2)
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
        copy = json.loads(raw)
        short = copy.get("short_message") or _FALLBACK["short_message"]
        return {
            "subject": copy.get("subject") or _FALLBACK["subject"],
            "body_html": copy.get("body_html") or _FALLBACK["body_html"],
            "short_message": _append_link(short),
        }
    except Exception as e:
        logger.error("generate_copy failed type=%s: %s", notification_type, e)
        fallback = dict(_FALLBACK)
        base = f"Hey {first}! Something new is waiting for you on ECALT." if first != "there" else _FALLBACK["short_message"]
        fallback["short_message"] = _append_link(base)
        return fallback


def _append_link(short: str) -> str:
    """Guarantee the ECALT /learn URL appears at the end of a WhatsApp short_message."""
    from app.core.config import settings
    frontend_url = (getattr(settings, "FRONTEND_URL", None) or "https://ecalt.vercel.app").rstrip("/")
    link = f"{frontend_url}/learn"
    if link in short or frontend_url in short:
        return short
    separator = " → "
    max_body = 160 - len(separator) - len(link)
    if len(short) > max_body:
        short = short[:max_body].rstrip() + "…"
    return f"{short}{separator}{link}"
