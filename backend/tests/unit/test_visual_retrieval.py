"""Visual Intelligence Layer (plans/visual-intelligence Phase 5): retrieval
abstraction + the registered Wikimedia Commons adapter's orchestration."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import visual_retrieval_service as retrieval
from app.services.visual_retrieval_service import LicenseMetadata, NormalizedVisualCandidate, VisualCandidate


class TestRegisteredAdapters:
    def test_wikimedia_commons_is_registered(self):
        assert "wikimedia_commons" in retrieval.SOURCE_ADAPTERS


class TestRetrieveLicensedAsset:
    @pytest.mark.asyncio
    async def test_returns_first_confident_candidate(self):
        good = NormalizedVisualCandidate(
            external_url="https://commons.example/good.jpg", width=800, height=600,
            license=LicenseMetadata(
                source="wikimedia_commons", source_url="https://commons.example/File:good.jpg",
                license="CC BY-SA 4.0", license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                commercial_use_allowed=True, modification_allowed=True, attribution_required=True,
            ),
        )
        fake_adapter = MagicMock()
        fake_adapter.search = AsyncMock(return_value=[VisualCandidate("https://x", 800, 600, {})])
        fake_adapter.normalize = MagicMock(return_value=good)

        with patch.object(retrieval, "SOURCE_ADAPTERS", {"wikimedia_commons": fake_adapter}):
            result = await retrieval.retrieve_licensed_asset("photosynthesis", "adults")

        assert result is good

    @pytest.mark.asyncio
    async def test_skips_low_confidence_candidates(self):
        bad = NormalizedVisualCandidate(
            external_url="https://commons.example/bad.jpg", width=800, height=600,
            license=LicenseMetadata(
                source="wikimedia_commons", source_url="x", license="CC BY-NC 2.0", license_url="x",
                commercial_use_allowed=False, modification_allowed=False, attribution_required=True,
            ),
        )
        fake_adapter = MagicMock()
        fake_adapter.search = AsyncMock(return_value=[VisualCandidate("https://x", 800, 600, {})])
        fake_adapter.normalize = MagicMock(return_value=bad)

        with patch.object(retrieval, "SOURCE_ADAPTERS", {"wikimedia_commons": fake_adapter}):
            result = await retrieval.retrieve_licensed_asset("photosynthesis", "adults")

        assert result is None

    @pytest.mark.asyncio
    async def test_adapter_error_does_not_raise(self):
        fake_adapter = MagicMock()
        fake_adapter.search = AsyncMock(side_effect=RuntimeError("network down"))

        with patch.object(retrieval, "SOURCE_ADAPTERS", {"wikimedia_commons": fake_adapter}):
            result = await retrieval.retrieve_licensed_asset("photosynthesis", "adults")

        assert result is None

    @pytest.mark.asyncio
    async def test_no_adapters_returns_none(self):
        with patch.object(retrieval, "SOURCE_ADAPTERS", {}):
            result = await retrieval.retrieve_licensed_asset("photosynthesis", "adults")
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
