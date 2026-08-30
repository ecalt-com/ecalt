"""Visual Intelligence Layer (plans/visual-intelligence Phase 6): image
generation gateway graceful degradation, mirroring test_journey_images.py's
coverage of the hero-image path."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services import visual_image_service


class TestGenerateStepVisual:
    @pytest.mark.asyncio
    async def test_storage_disabled_returns_none_without_calling_provider(self):
        with (
            patch("app.services.visual_image_service.images_enabled", return_value=False),
            patch("app.services.visual_image_service.generate_visual_image", new=AsyncMock()) as mock_gen,
        ):
            result = await visual_image_service.generate_step_visual("a leaf absorbing sunlight", uid="u1")
        assert result is None
        mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_budget_exhausted_returns_none(self):
        with (
            patch("app.services.visual_image_service.images_enabled", return_value=True),
            patch("app.services.subscription_service.check_budget", return_value=(False, "exhausted")),
            patch("app.services.visual_image_service.generate_visual_image", new=AsyncMock()) as mock_gen,
        ):
            result = await visual_image_service.generate_step_visual("a leaf", uid="u1")
        assert result is None
        mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_returns_url_and_metadata(self):
        with (
            patch("app.services.visual_image_service.images_enabled", return_value=True),
            patch("app.services.subscription_service.check_budget", return_value=(True, "")),
            patch("app.services.subscription_service.record_image_usage") as mock_record,
            patch(
                "app.services.visual_image_service.generate_visual_image",
                new=AsyncMock(return_value=(b"fake-bytes", "gpt-image-1-mini", "image/webp")),
            ),
            patch(
                "app.services.visual_image_service.upload_visual_image",
                new=AsyncMock(return_value="https://storage.example/visual-assets/abc.webp"),
            ),
        ):
            result = await visual_image_service.generate_step_visual("a leaf absorbing sunlight", uid="u1")
        assert result["url"] == "https://storage.example/visual-assets/abc.webp"
        assert result["model"] == "gpt-image-1-mini"
        assert result["size_bytes"] == len(b"fake-bytes")
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs.get("interaction_type") == "visual_image"

    @pytest.mark.asyncio
    async def test_provider_error_returns_none(self):
        with (
            patch("app.services.visual_image_service.images_enabled", return_value=True),
            patch("app.services.subscription_service.check_budget", return_value=(True, "")),
            patch(
                "app.services.visual_image_service.generate_visual_image",
                new=AsyncMock(side_effect=RuntimeError("provider down")),
            ),
        ):
            result = await visual_image_service.generate_step_visual("a leaf", uid="u1")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_uid_skips_budget_check_but_still_generates(self):
        with (
            patch("app.services.visual_image_service.images_enabled", return_value=True),
            patch(
                "app.services.visual_image_service.generate_visual_image",
                new=AsyncMock(return_value=(b"bytes", "gpt-image-1-mini", "image/webp")),
            ),
            patch(
                "app.services.visual_image_service.upload_visual_image",
                new=AsyncMock(return_value="https://storage.example/x.webp"),
            ),
        ):
            result = await visual_image_service.generate_step_visual("a leaf", uid=None)
        assert result is not None


class TestVideoServiceStub:
    @pytest.mark.asyncio
    async def test_always_returns_none(self):
        from app.services import visual_video_service
        assert visual_video_service.VIDEO_PROVIDERS == {}
        result = await visual_video_service.generate_step_video("a rocket launching", uid="u1")
        assert result is None
