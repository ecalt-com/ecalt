"""Visual Intelligence Layer — Phase 5: retrieval abstraction + Wikimedia Commons.

Spec section 20 is explicit: "Do not add sources to production until their
licensing and API/use terms are reviewed for ECALT's intended commercial
use... Google Images must not be treated as a production free-media source."

Wikimedia Commons is the one source reviewed for this: every upload carries
a machine-readable license in its metadata, the public API needs no key, and
license_confidence_ok() below still gates every individual image before it
can become a VLO -- an unrecognized or non-commercial license is excluded
per-image, not just per-source. See wikimedia_retrieval_adapter.py for the
license-string parsing.

Not covered: content-safety moderation. Commons has no equivalent of
SafeSearch, so visual_orchestrator_service._try_retrieval only calls this
for grade_band == "adults" -- do not widen that gate without adding real
content moderation first. A second source needs the same review before
being added to SOURCE_ADAPTERS.
"""
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class LicenseMetadata:
    source: str
    source_url: str
    license: str
    license_url: str
    commercial_use_allowed: bool
    modification_allowed: bool
    attribution_required: bool
    attribution: str = ""


@dataclass
class VisualCandidate:
    external_url: str
    width: Optional[int]
    height: Optional[int]
    raw: dict


@dataclass
class NormalizedVisualCandidate:
    external_url: str
    width: Optional[int]
    height: Optional[int]
    license: LicenseMetadata


class VisualSourceAdapter(Protocol):
    name: str

    async def search(self, query: str, grade_band: str) -> list[VisualCandidate]: ...
    def normalize(self, candidate: VisualCandidate) -> NormalizedVisualCandidate: ...


# Imported here (not at module top) to avoid a circular import --
# wikimedia_retrieval_adapter.py imports the dataclasses defined above.
from app.services.wikimedia_retrieval_adapter import WikimediaCommonsAdapter  # noqa: E402

# Populate only after a source's licensing + commercial-use terms have been
# reviewed for ECALT (spec sections 20-21).
SOURCE_ADAPTERS: dict[str, VisualSourceAdapter] = {
    "wikimedia_commons": WikimediaCommonsAdapter(),
}


def license_confidence_ok(license: LicenseMetadata) -> bool:
    """Spec section 21: if license status can't be determined with
    sufficient confidence, do not auto-publish -- leave it in a
    blocked/pending state instead. v1's bar: commercial use must be
    explicitly allowed and both the license name and its URL must be
    present."""
    return bool(license.commercial_use_allowed and license.license and license.license_url)


async def retrieve_licensed_asset(query: str, grade_band: str) -> Optional[NormalizedVisualCandidate]:
    """Never raises. Returns None when no adapter is registered, every
    adapter errors, or nothing found passes the license-confidence check --
    the orchestrator treats None as 'fall through to the next strategy'
    (spec section 27: retrieval failure -> try next strategy)."""
    for adapter in SOURCE_ADAPTERS.values():
        try:
            candidates = await adapter.search(query, grade_band)
        except Exception:
            continue
        for candidate in candidates:
            normalized = adapter.normalize(candidate)
            if license_confidence_ok(normalized.license):
                return normalized
    return None
