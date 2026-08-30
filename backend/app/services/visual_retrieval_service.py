"""Visual Intelligence Layer — Phase 5: retrieval abstraction (interface only).

Spec section 20 is explicit: "Do not add sources to production until their
licensing and API/use terms are reviewed for ECALT's intended commercial
use... Google Images must not be treated as a production free-media source."

No concrete source adapter is registered here — this ships the interface and
license-confidence check so a reviewed, approved source (Wikimedia Commons,
Openverse, a licensed stock API, etc.) can be wired in later without
touching the router or orchestrator again. SOURCE_ADAPTERS is empty by
design, so retrieve_licensed_asset() always returns None today regardless of
VISUAL_RETRIEVAL_ENABLED — there is nothing to retrieve from yet.
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


# Populate only after a source's licensing + commercial-use terms have been
# reviewed for ECALT (spec sections 20-21). Empty by design in v1.
SOURCE_ADAPTERS: dict[str, VisualSourceAdapter] = {}


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
