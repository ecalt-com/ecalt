"""Link previews for shared journeys (F1.6).

WhatsApp, Facebook, X, Slack, Telegram and Discord don't run JavaScript, so a
shared /journey/<id> link only ever showed the generic site card. Vercel routes
those crawlers (by user agent) here; people still get the normal SPA.
"""
import html
import re
from typing import Optional

from fastapi import APIRouter, Response

from app.core.database import get_db
from app.services.notification_links import frontend_url

router = APIRouter()

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_GENERIC_TITLE = "ECALT — Turn Curiosity Into Capability"
_GENERIC_DESC = "Ask any question, get a personalized AI-powered learning journey."


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _lookup(journey_id: str) -> Optional[dict]:
    """Title, description and image for a journey that is safe to show publicly.

    School courses and journeys owned by a family child profile get the generic
    card: their titles aren't ours to put on a public page.
    """
    if not _SAFE_ID.match(journey_id):
        return None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.title, j.description, j.hero_image_url, j.school_id, u.profile_type
                  FROM journeys j LEFT JOIN users u ON u.uid = j.uid
                 WHERE j.id = %s
                """,
                (journey_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    if row["school_id"] is not None or (row["profile_type"] or "account") != "account":
        return {"generic": True}
    return dict(row)


def render_card(journey_id: str, row: Optional[dict]) -> str:
    base = frontend_url()
    url = f"{base}/journey/{journey_id}" if _SAFE_ID.match(journey_id) else base
    generic = not row or row.get("generic")
    title = _GENERIC_TITLE if generic else f"{_clip(row['title'], 90)} — ECALT"
    desc = _GENERIC_DESC if generic else _clip(row.get("description") or _GENERIC_DESC, 200)
    image = row.get("hero_image_url") if not generic else None
    if not image or not str(image).startswith("https://"):
        image = f"{base}/og-image.png"
    e = html.escape
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{e(title)}</title>
<meta name="description" content="{e(desc, quote=True)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ECALT">
<meta property="og:title" content="{e(title, quote=True)}">
<meta property="og:description" content="{e(desc, quote=True)}">
<meta property="og:image" content="{e(image, quote=True)}">
<meta property="og:url" content="{e(url, quote=True)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title, quote=True)}">
<meta name="twitter:description" content="{e(desc, quote=True)}">
<meta name="twitter:image" content="{e(image, quote=True)}">
</head><body><h1>{e(title)}</h1><p>{e(desc)}</p><p><a href="{e(url, quote=True)}">Open on ECALT</a></p></body></html>"""


@router.get("/journey/{journey_id}", include_in_schema=False)
def share_journey(journey_id: str):
    try:
        row = _lookup(journey_id)
    except Exception:
        row = None
    return Response(content=render_card(journey_id, row), media_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "public, max-age=3600"})
