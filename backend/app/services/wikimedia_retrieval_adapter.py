"""Visual Intelligence Layer — Phase 5: Wikimedia Commons retrieval adapter.

The one source the spec's section 20 caution ("do not add sources to
production until license review") has been reviewed for: Commons requires
every upload to carry a machine-readable license in its metadata
(extmetadata.LicenseShortName/LicenseUrl), and the public API needs no key
and no per-request fee, so it's the lowest-risk source to start with.

Not reviewed/covered by this adapter: content-safety moderation. Commons is
open, user-uploaded media with no equivalent of Google's SafeSearch -- so
the orchestrator only calls retrieval for grade_band == "adults"
(visual_orchestrator_service._try_retrieval). Do not widen that gate without
adding real content moderation first.
"""
import html
import logging
import re

import httpx

from app.services.visual_retrieval_service import LicenseMetadata, NormalizedVisualCandidate, VisualCandidate

logger = logging.getLogger(__name__)

_API_URL = "https://commons.wikimedia.org/w/api.php"
# Wikimedia's API etiquette requires a descriptive User-Agent identifying the
# application (see https://meta.wikimedia.org/wiki/User-Agent_policy).
_USER_AGENT = "ECALT-VisualIntelligence/1.0 (https://ecalt.app; educational content platform)"
_RESULT_LIMIT = 8


def _parse_license(license_short_name: str) -> tuple[bool, bool]:
    """Returns (commercial_use_allowed, modification_allowed) from a Commons
    LicenseShortName string ("CC BY-SA 4.0", "Public domain", "CC BY-NC 2.0").

    Conservative allowlist, not a denylist: an unrecognized string returns
    (False, False) so license_confidence_ok() excludes it rather than
    guessing (spec section 21).
    """
    normalized = license_short_name.strip().lower()
    if not normalized:
        return False, False
    if "nc" in normalized:  # any non-commercial variant (CC BY-NC, CC BY-NC-SA, ...)
        return False, False
    if normalized.startswith("cc0") or "public domain" in normalized or normalized.startswith("pd"):
        return True, True
    if normalized.startswith("cc by"):
        modification_allowed = "nd" not in normalized  # CC BY-ND forbids derivative works
        return True, modification_allowed
    return False, False


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(value)).strip()


class WikimediaCommonsAdapter:
    name = "wikimedia_commons"

    async def search(self, query: str, grade_band: str) -> list[VisualCandidate]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",  # File namespace
            "gsrlimit": str(_RESULT_LIMIT),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
        }
        try:
            async with httpx.AsyncClient(timeout=10, headers={"User-Agent": _USER_AGENT}) as client:
                resp = await client.get(_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("wikimedia commons search failed for query=%r", query, exc_info=True)
            return []

        pages = (data.get("query") or {}).get("pages") or {}
        candidates: list[VisualCandidate] = []
        for page in pages.values():
            imageinfo = (page.get("imageinfo") or [None])[0]
            if not imageinfo or not str(imageinfo.get("mime", "")).startswith("image/"):
                continue
            candidates.append(VisualCandidate(
                external_url=imageinfo.get("url", ""),
                width=imageinfo.get("width"),
                height=imageinfo.get("height"),
                raw=imageinfo,
            ))
        return candidates

    def normalize(self, candidate: VisualCandidate) -> NormalizedVisualCandidate:
        meta = candidate.raw.get("extmetadata") or {}

        def field(key: str) -> str:
            entry = meta.get(key)
            return entry.get("value", "") if isinstance(entry, dict) else ""

        license_short = field("LicenseShortName")
        license_url = field("LicenseUrl")
        artist = _strip_html(field("Artist")) or "Wikimedia Commons contributor"
        commercial_use_allowed, modification_allowed = _parse_license(license_short)

        return NormalizedVisualCandidate(
            external_url=candidate.external_url,
            width=candidate.width,
            height=candidate.height,
            license=LicenseMetadata(
                source="wikimedia_commons",
                source_url=candidate.raw.get("descriptionurl", candidate.external_url),
                license=license_short or "unknown",
                license_url=license_url,
                commercial_use_allowed=commercial_use_allowed,
                modification_allowed=modification_allowed,
                attribution_required=True,  # every non-CC0/PD Commons license requires attribution
                attribution=artist,
            ),
        )
