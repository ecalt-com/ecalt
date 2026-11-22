"""Signed click-through links for notifications (F1.4).

An email or WhatsApp call to action points at /api/v1/notifications/c/{log_id}
?to=<path>&sig=<hmac>. The endpoint stamps notification_log.clicked_at and
redirects to the path on the frontend, so we can tell whether the message or
the landing page is failing. The target is signed and must be a same-site
relative path, so the link can never be turned into an open redirect.
"""
import hashlib
import hmac
from typing import Optional
from urllib.parse import quote

from app.core.config import settings


def _secret() -> bytes:
    return (settings.NOTIFICATION_SIGNING_SECRET or "ecalt-unsub-secret").encode()


def frontend_url() -> str:
    return (getattr(settings, "FRONTEND_URL", None) or "https://ecalt.vercel.app").rstrip("/")


def is_safe_target(path: str) -> bool:
    """Same-site relative path only: '/x', never '//host', a scheme, a backslash or control characters."""
    return (
        bool(path) and len(path) <= 300 and path.startswith("/") and not path.startswith("//")
        and "\\" not in path and ":" not in path.split("?", 1)[0].split("#", 1)[0]
        and all(32 <= ord(c) < 127 for c in path)
    )


def sign_click(log_id: str, target: str) -> str:
    return hmac.new(_secret(), f"click|{log_id}|{target}".encode(), hashlib.sha256).hexdigest()


def verify_click(log_id: str, target: str, sig: str) -> bool:
    return is_safe_target(target) and hmac.compare_digest(sign_click(log_id, target), sig or "")


def build_click_url(log_id: str, target: str) -> str:
    return f"{frontend_url()}/api/v1/notifications/c/{log_id}?to={quote(target, safe='')}&sig={sign_click(log_id, target)}"


def landing_url(target: str, channel: Optional[str], notification_type: Optional[str]) -> str:
    """Frontend URL for a verified target, with utm parameters placed before any #fragment."""
    path, _, fragment = target.partition("#")
    sep = "&" if "?" in path else "?"
    utm = f"utm_source=notif&utm_medium={quote(channel or 'unknown')}&utm_campaign={quote(notification_type or 'unknown')}"
    return f"{frontend_url()}{path}{sep}{utm}" + (f"#{fragment}" if fragment else "")


def target_path(notification_type: str, context: dict) -> str:
    """Where a notification should land: the exact step to resume, a review, or /learn."""
    journey_id, step_id = context.get("journey_id"), context.get("next_step_id")
    if notification_type in ("journey_almost_done", "milestone_approach") and journey_id:
        path = f"/journey/{quote(str(journey_id), safe='')}"
        return path + (f"#step-{quote(str(step_id), safe='')}" if step_id else "")
    if notification_type == "review_due":
        return "/review"
    return "/learn"
