"""Visual Intelligence Layer — Phase 6: image generation gateway.

Modeled directly on app/services/image_service.py (hero images) — same
client, same budget-check-before-spend pattern, same "never raise, degrade
silently" contract. The one difference: hero images are keyed by journey_id
(one per journey), these are keyed by content hash (shareable across any
step that plans the same concept/description), matching how a VLO is meant
to be reusable (spec section 4).

Disabled unless SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY are set (same gate
image_service uses) AND VISUAL_IMAGE_GENERATION_ENABLED is true — the
orchestrator checks the flag; images_enabled() here checks storage.
"""
import base64
import hashlib
import logging

import httpx

from app.core.config import settings
from app.services.provider_service import _get_openai, get_config

logger = logging.getLogger(__name__)

_BUCKET = "visual-assets"
_IMAGE_SIZE = "1024x1024"
_IMAGE_QUALITY = "low"  # step illustrations are smaller/cheaper than hero images

_VISUAL_STYLE = (
    "Flat modern educational illustration, minimal vector style, soft gradient "
    "background, 2-4 harmonious colors, one clear central visual metaphor. "
    "Strictly no text, no letters, no numbers, no watermarks, no logos, "
    "no real people or recognizable likenesses."
)


def images_enabled() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _prompt(visual_description: str) -> str:
    return f"{visual_description.strip()}. {_VISUAL_STYLE}"


async def generate_visual_image(visual_description: str) -> tuple[bytes, str, str]:
    """Generate an image; returns (bytes, model, content_type). Raises on failure."""
    cfg = get_config("visual_image")
    model = cfg["model"]
    client = _get_openai()
    kwargs: dict = {"model": model, "prompt": _prompt(visual_description), "size": _IMAGE_SIZE, "n": 1}
    if model.startswith("gpt-image"):
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


async def upload_visual_image(content_hash: str, data: bytes, content_type: str = "image/webp") -> str:
    """Content-addressed upload — same description hashes to the same path,
    so re-planning an identical visual reuses the object instead of
    re-uploading (mirrors the VLO reuse principle at the storage layer)."""
    ext = content_type.rsplit("/", 1)[-1]
    path = f"{content_hash}.{ext}"
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


async def generate_step_visual(visual_description: str, uid: str | None) -> dict | None:
    """Budget-checked, best-effort. Returns
    {"url", "model", "content_type", "content_hash"} on success, None on any
    failure (storage disabled, budget exhausted, provider error) -- callers
    must treat None as "fall back to a cheaper strategy" (spec section 27)."""
    from app.services.subscription_service import check_budget, record_image_usage

    if not images_enabled():
        logger.debug("visual image generation skipped: storage not configured")
        return None
    try:
        if uid:
            allowed, _ = check_budget(uid)
            if not allowed:
                logger.info("visual image generation skipped: budget exhausted uid=%s", uid)
                return None
        data, model, content_type = await generate_visual_image(visual_description)
        content_hash = hashlib.sha256(data).hexdigest()[:16]
        url = await upload_visual_image(content_hash, data, content_type)
        if uid:
            record_image_usage(uid, model, interaction_type="visual_image")
        return {"url": url, "model": model, "content_type": content_type, "content_hash": content_hash,
                "size_bytes": len(data)}
    except Exception:
        logger.warning("visual image generation failed", exc_info=True)
        return None
