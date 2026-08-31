"""Visual Intelligence Layer (plans/visual-intelligence Phase 5): Wikimedia
Commons adapter — license-string parsing (the actual safety gate) and the
search/normalize contract."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.visual_retrieval_service import VisualCandidate
from app.services.wikimedia_retrieval_adapter import WikimediaCommonsAdapter, _parse_license


class TestParseLicense:
    @pytest.mark.parametrize("license_str,expected", [
        ("CC0", (True, True)),
        ("Public domain", (True, True)),
        ("PD-old", (True, True)),
        ("CC BY 4.0", (True, True)),
        ("CC BY-SA 4.0", (True, True)),
        ("CC BY 2.0", (True, True)),
        ("CC BY-ND 4.0", (True, False)),
        ("CC BY-NC 2.0", (False, False)),
        ("CC BY-NC-SA 4.0", (False, False)),
        ("CC BY-NC-ND 4.0", (False, False)),
        ("", (False, False)),
        ("some unrecognized string", (False, False)),
    ])
    def test_parses_expected_permissions(self, license_str, expected):
        assert _parse_license(license_str) == expected


class TestNormalize:
    def test_extracts_license_and_strips_artist_html(self):
        candidate = VisualCandidate(
            external_url="https://upload.wikimedia.org/x.jpg", width=800, height=600,
            raw={
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:x.jpg",
                "extmetadata": {
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                    "Artist": {"value": '<a href="https://x">Jane Doe</a>'},
                },
            },
        )
        normalized = WikimediaCommonsAdapter().normalize(candidate)
        assert normalized.license.license == "CC BY-SA 4.0"
        assert normalized.license.commercial_use_allowed is True
        assert normalized.license.attribution == "Jane Doe"
        assert normalized.license.source_url == "https://commons.wikimedia.org/wiki/File:x.jpg"

    def test_missing_metadata_defaults_to_unconfident(self):
        candidate = VisualCandidate(external_url="https://x", width=None, height=None, raw={})
        normalized = WikimediaCommonsAdapter().normalize(candidate)
        assert normalized.license.commercial_use_allowed is False
        assert normalized.license.license == "unknown"


class TestSearch:
    @pytest.mark.asyncio
    async def test_filters_non_image_mime_and_maps_fields(self):
        fake_response = MagicMock()
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {
            "query": {
                "pages": {
                    "1": {"imageinfo": [{"url": "https://x/a.jpg", "width": 800, "height": 600, "mime": "image/jpeg"}]},
                    "2": {"imageinfo": [{"url": "https://x/a.pdf", "width": 10, "height": 10, "mime": "application/pdf"}]},
                    "3": {},
                }
            }
        }
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(return_value=fake_response)
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.wikimedia_retrieval_adapter.httpx.AsyncClient", return_value=fake_client):
            candidates = await WikimediaCommonsAdapter().search("photosynthesis", "adults")

        assert len(candidates) == 1
        assert candidates[0].external_url == "https://x/a.jpg"

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_list(self):
        fake_client = AsyncMock()
        fake_client.get = AsyncMock(side_effect=RuntimeError("network down"))
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.wikimedia_retrieval_adapter.httpx.AsyncClient", return_value=fake_client):
            candidates = await WikimediaCommonsAdapter().search("photosynthesis", "adults")

        assert candidates == []
