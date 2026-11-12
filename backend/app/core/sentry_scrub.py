"""Keep personal data out of Sentry (compliance memo G4, SC-805).

Init options do most of it: no request bodies, no cookies/IPs, no local
variables in stack frames. `scrub_event` then strips query strings, auth and
profile headers, the user, and redacts student ids and email addresses in
messages and breadcrumbs. School routes are tagged with `school_id` only.
"""
from __future__ import annotations

import re
from typing import Any, Optional

_SENSITIVE_HEADERS = re.compile(r"authorization|cookie|x-parent-unlock|x-profile-id|x-impersonate|x-forwarded-for|"
                                r"x-real-ip|x-vercel-protection-bypass", re.I)
_SCHOOL_PATH = re.compile(r"/schools/([0-9a-f-]{36})(?:/|$)", re.I)
_STUDENT_UID = re.compile(r"\bstu_[0-9a-z]+\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def init_options() -> dict:
    return {
        "send_default_pii": False,
        "max_request_body_size": "never",
        "include_local_variables": False,
        "before_send": scrub_event,
        "before_send_transaction": scrub_event,
        "before_breadcrumb": scrub_breadcrumb,
    }


def _redact(text: Any) -> Any:
    if not isinstance(text, str):
        return text
    return _EMAIL.sub("[email]", _STUDENT_UID.sub("stu_[redacted]", text))


def _strip_url(url: Optional[str]) -> Optional[str]:
    return url.split("?", 1)[0].split("#", 1)[0] if isinstance(url, str) else url


def scrub_event(event: dict, hint: Optional[dict] = None) -> dict:
    req = event.get("request")
    if isinstance(req, dict):
        url = req.get("url")
        m = _SCHOOL_PATH.search(url or "")
        if m:
            event.setdefault("tags", {})["school_id"] = m.group(1)
        req["url"] = _STUDENT_UID.sub("stu_[redacted]", _strip_url(url) or "") or url
        for key in ("query_string", "data", "cookies", "env"):
            req.pop(key, None)
        headers = req.get("headers")
        if isinstance(headers, dict):
            req["headers"] = {k: v for k, v in headers.items() if not _SENSITIVE_HEADERS.search(k)}
    event.pop("user", None)
    if "transaction" in event:
        event["transaction"] = _redact(event["transaction"])
    if isinstance(event.get("message"), str):
        event["message"] = _redact(event["message"])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        logentry["message"] = _redact(logentry.get("message"))
        logentry.pop("params", None)
    for exc in (event.get("exception") or {}).get("values") or []:
        exc["value"] = _redact(exc.get("value"))
    crumbs = event.get("breadcrumbs")
    values = crumbs.get("values") if isinstance(crumbs, dict) else crumbs
    for crumb in values or []:
        scrub_breadcrumb(crumb)
    return event


def scrub_breadcrumb(crumb: dict, hint: Optional[dict] = None) -> dict:
    crumb["message"] = _redact(crumb.get("message"))
    data = crumb.get("data")
    if isinstance(data, dict):
        for key in ("url", "http.query", "http.fragment"):
            if key in data:
                data[key] = _redact(_strip_url(data[key])) if key == "url" else None
    return crumb
