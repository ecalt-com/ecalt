"""Supabase Storage access for the private `school-materials` bucket (README §3.6).

Uploaded source documents (PDF/DOCX) go straight from the browser to Storage
via a short-lived **signed upload URL** so a 25 MB file never has to pass through
the Vercel-rewrite → Railway request path. This module mints those URLs and, on
`complete`, downloads the object server-side to verify it. Deleting a document
removes its object here.

Needs `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`; without them the document
endpoints return 503 (the feature is simply off), exactly like journey images.
The bucket must be **private** (create it once in the Supabase dashboard; objects
are only ever reached with the service-role key or a signed URL).
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)


class StorageUnavailable(Exception):
    """Storage isn't configured (missing Supabase env). Maps to 503."""


class StorageError(Exception):
    """A Storage call failed (network or non-2xx)."""


def storage_enabled() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _require() -> None:
    if not storage_enabled():
        raise StorageUnavailable("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")


def _base() -> str:
    return settings.SUPABASE_URL.rstrip("/")


def _bucket() -> str:
    return settings.SCHOOL_MATERIALS_BUCKET


def _auth() -> dict:
    # Both headers: the new `sb_secret_...` keys authenticate via `apikey` (the
    # Storage gateway rejects them as a Bearer JWT otherwise), while legacy
    # service-role JWTs accept either — so sending both works for any key format.
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    return {"Authorization": f"Bearer {key}", "apikey": key}


def signed_upload_url(object_path: str, *, upsert: bool = True) -> dict:
    """Create a one-time signed URL the browser PUTs the file to. Returns
    ``{"upload_url", "token", "path"}``; the browser sends the raw bytes to
    ``upload_url`` (no credentials — the token is embedded)."""
    _require()
    url = f"{_base()}/storage/v1/object/upload/sign/{_bucket()}/{object_path}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as http:
            resp = http.post(url, headers={**_auth(), "x-upsert": "true" if upsert else "false"})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise StorageError(f"signed upload URL failed: {exc}") from exc
    # Supabase returns {"url": "/object/upload/sign/<bucket>/<path>?token=<jwt>"}.
    signed = data.get("url") or ""
    token = signed.split("token=", 1)[1] if "token=" in signed else data.get("token", "")
    return {"upload_url": f"{_base()}/storage/v1{signed}", "token": token, "path": object_path}


def download(object_path: str) -> bytes:
    """Fetch the stored object's bytes (used by `complete` to verify the file)."""
    _require()
    url = f"{_base()}/storage/v1/object/{_bucket()}/{object_path}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as http:
            resp = http.get(url, headers=_auth())
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPError as exc:
        raise StorageError(f"download failed: {exc}") from exc


def delete(object_path: str) -> None:
    """Remove the stored object. A missing object is treated as already gone."""
    _require()
    url = f"{_base()}/storage/v1/object/{_bucket()}/{object_path}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as http:
            resp = http.delete(url, headers=_auth())
            if resp.status_code == 404:
                return
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        # A delete failure shouldn't block the DB soft-delete; log and move on.
        logger.warning("storage delete failed for %s: %s", object_path, exc)
