"""Journey hero images: generate with an image model, store in Supabase Storage.

Everything here is best-effort — a journey without a hero image renders its
emoji icon, so no failure in this module may ever surface to the learner.
Disabled entirely unless SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set.
"""

import base64
import logging

import httpx

from app.core.config import settings
from app.models.schemas import Journey
from app.services.provider_service import _get_openai, get_config

logger = logging.getLogger(__name__)

_BUCKET = "journey-images"
_IMAGE_SIZE = "1024x1024"
# COST_PER_IMAGE in provider_service prices this quality tier — change both together.
_IMAGE_QUALITY = "medium"

# Fixed house style. The learner's raw question never reaches the image prompt —
# only the model-generated title/description/tags, which check_topic_scope and
# journey generation have already constrained to educational topics.
_HERO_STYLE = (
    "Flat modern educational illustration for a learning-app course card. "
    "Minimal vector style, soft gradient background, 2-4 harmonious colors, "
    "one clear central visual metaphor, generous negative space. "
    "Strictly no text, no letters, no numbers, no watermarks, no logos, "
    "no real people or recognizable likenesses."
)

_AGE_STYLE = {
    "kids":  "Playful, rounded, bright and friendly — suitable for children.",
    "teens": "Energetic and contemporary, slightly stylized.",
}


def _hero_prompt(journey: Journey) -> str:
    parts = [
        f"Course topic: {journey.title}.",
        f"What it teaches: {journey.description}",
    ]
    if journey.tags:
        parts.append(f"Themes: {', '.join(journey.tags[:4])}.")
    age_note = _AGE_STYLE.get(journey.age_group)
    if age_note:
        parts.append(age_note)
    parts.append(_HERO_STYLE)
    return " ".join(parts)


def images_enabled() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


async def generate_hero_image(journey: Journey) -> tuple[bytes, str, str]:
    """Generate a hero image; returns (bytes, model, content_type). Raises on failure."""
    cfg = get_config("journey_image")
    model = cfg["model"]
    client = _get_openai()
    kwargs: dict = {
        "model": model,
        "prompt": _hero_prompt(journey),
        "size": _IMAGE_SIZE,
        "n": 1,
    }
    if model.startswith("gpt-image"):
        # gpt-image-* always returns b64 and supports native webp output.
        kwargs["quality"] = _IMAGE_QUALITY
        kwargs["output_format"] = "webp"
        content_type = "image/webp"
    else:
        kwargs["response_format"] = "b64_json"
        content_type = "image/png"
    resp = await client.images.generate(**kwargs)
    b64 = resp.data[0].b64_json
    if not b64:
        raise ValueError("image API returned no b64 payload")
    return base64.b64decode(b64), model, content_type


async def upload_journey_image(journey_id: str, data: bytes, content_type: str = "image/webp") -> str:
    """Upload to the public journey-images bucket; returns the public URL."""
    ext = content_type.rsplit("/", 1)[-1]
    path = f"{journey_id}.{ext}"
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            f"{settings.SUPABASE_URL}/storage/v1/object/{_BUCKET}/{path}",
            content=data,
            headers={
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "true",
                "cache-control": "max-age=31536000",
            },
        )
        resp.raise_for_status()
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{_BUCKET}/{path}"


def _save_hero_url(journey_id: str, url: str) -> None:
    from app.core.database import get_db
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE journeys SET hero_image_url = %s WHERE id = %s",
                (url, journey_id),
            )


async def generate_and_attach_hero(journey: Journey, uid: str | None) -> str | None:
    """Background task: hero image for a freshly persisted journey. Never raises.

    Budget-checked and debited like any other AI call; on any failure the
    journey simply keeps its emoji icon.
    """
    from app.services.subscription_service import check_budget, record_image_usage

    if not images_enabled():
        logger.debug("hero image skipped: storage not configured")
        return None
    try:
        if uid:
            allowed, _ = check_budget(uid)
            if not allowed:
                logger.info("hero image skipped: budget exhausted uid=%s", uid)
                return None
        data, model, content_type = await generate_hero_image(journey)
        url = await upload_journey_image(journey.id, data, content_type)
        _save_hero_url(journey.id, url)
        if uid:
            record_image_usage(uid, model)
        logger.info("hero image attached journey=%s bytes=%d", journey.id, len(data))
        return url
    except Exception:
        logger.warning("hero image generation failed journey=%s", journey.id, exc_info=True)
        return None
