"""Visual Intelligence Layer (plans/visual-intelligence Phase 5): retrieval
abstraction. No adapter is registered in v1, so retrieval must always
degrade to None regardless of what's asked for."""
import pytest

from app.services import visual_retrieval_service as retrieval
from app.services.visual_retrieval_service import LicenseMetadata


class TestNoAdaptersRegistered:
    @pytest.mark.asyncio
    async def test_retrieval_always_returns_none(self):
        assert retrieval.SOURCE_ADAPTERS == {}
        result = await retrieval.retrieve_licensed_asset("photosynthesis diagram", "6-8")
        assert result is None


class TestLicenseConfidence:
    def test_fully_specified_permissive_license_passes(self):
        license = LicenseMetadata(
            source="wikimedia", source_url="https://commons.wikimedia.org/x",
            license="CC BY-SA 4.0", license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            commercial_use_allowed=True, modification_allowed=True, attribution_required=True,
        )
        assert retrieval.license_confidence_ok(license) is True

    def test_commercial_use_disallowed_fails(self):
        license = LicenseMetadata(
            source="x", source_url="x", license="CC BY-NC", license_url="https://x",
            commercial_use_allowed=False, modification_allowed=True, attribution_required=True,
        )
        assert retrieval.license_confidence_ok(license) is False

    def test_missing_license_url_fails(self):
        license = LicenseMetadata(
            source="x", source_url="x", license="CC BY", license_url="",
            commercial_use_allowed=True, modification_allowed=True, attribution_required=True,
        )
        assert retrieval.license_confidence_ok(license) is False
