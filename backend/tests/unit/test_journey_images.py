"""Journey images (plans/journey-images): SVG sanitizer, image cost table, hero prompts."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.journeys import SAMPLE_JOURNEYS
from app.services.ai_service import sanitize_step_diagrams, _svg_is_safe
from app.services.image_service import _hero_prompt, generate_hero_image
from app.services.provider_service import COST_PER_IMAGE, cost_for_images


SAFE_SVG = (
    '<svg viewBox="0 0 640 360" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="10" y="10" width="100" height="50" fill="#eee"/>'
    '<text x="20" y="40">Nucleus</text>'
    '<line x1="0" y1="0" x2="10" y2="10" stroke="black"/>'
    "</svg>"
)


class TestSvgSanitizer:
    def test_safe_svg_is_kept(self):
        content = f"Intro paragraph.\n\n{SAFE_SVG}\n\nMore prose."
        assert SAFE_SVG in sanitize_step_diagrams(content)

    def test_script_tag_dropped(self):
        svg = '<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>'
        assert "<svg" not in sanitize_step_diagrams(f"before\n{svg}\nafter")

    def test_event_handler_dropped(self):
        svg = '<svg viewBox="0 0 10 10"><rect onclick="steal()" width="5" height="5"/></svg>'
        assert "<svg" not in sanitize_step_diagrams(svg)

    def test_href_dropped(self):
        svg = ('<svg viewBox="0 0 10 10" xmlns:xlink="http://www.w3.org/1999/xlink">'
               '<text xlink:href="https://evil.example">x</text></svg>')
        assert "<svg" not in sanitize_step_diagrams(svg)

    def test_foreignobject_dropped(self):
        svg = "<svg><foreignObject><body>html</body></foreignObject></svg>"
        assert "<svg" not in sanitize_step_diagrams(svg)

    def test_malformed_svg_dropped_prose_kept(self):
        content = "Prose stays.\n<svg viewBox='0 0 10 10'><rect></svg>\nEnd."
        out = sanitize_step_diagrams(content)
        assert "<svg" not in out
        assert "Prose stays." in out and "End." in out

    def test_only_first_safe_svg_kept(self):
        out = sanitize_step_diagrams(f"{SAFE_SVG}\n\n{SAFE_SVG}")
        assert out.count("<svg") == 1

    def test_mermaid_block_untouched(self):
        content = "Look:\n\n```mermaid\nflowchart TD\n  A-->B\n```\n\nDone."
        assert sanitize_step_diagrams(content) == content

    def test_javascript_url_in_attr_rejected(self):
        assert not _svg_is_safe('<svg><rect fill="javascript:alert(1)"/></svg>')


class TestImageCosts:
    def test_known_models_priced(self):
        assert cost_for_images("gpt-image-1-mini") == COST_PER_IMAGE["gpt-image-1-mini"]
        assert cost_for_images("gpt-image-1", 3) == COST_PER_IMAGE["gpt-image-1"] * 3

    def test_unknown_model_uses_conservative_default(self):
        # Unknown image models must not be billed as free.
        assert cost_for_images("some-future-model") >= 1.0


class TestHeroPrompt:
    def test_prompt_carries_title_and_house_style(self):
        j = SAMPLE_JOURNEYS[0]
        prompt = _hero_prompt(j)
        assert j.title in prompt
        assert "no text" in prompt
        assert "no real people" in prompt

    def test_kids_age_group_gets_kid_style(self):
        j = SAMPLE_JOURNEYS[0].model_copy(update={"age_group": "kids"})
        assert "children" in _hero_prompt(j)


class TestGenerateHeroImage:
    @pytest.mark.asyncio
    async def test_gpt_image_request_shape(self):
        fake_resp = MagicMock()
        fake_resp.data = [MagicMock(b64_json="aGVsbG8=")]  # "hello"
        client = MagicMock()
        client.images.generate = AsyncMock(return_value=fake_resp)
        with patch("app.services.image_service.get_config",
                   return_value={"provider": "openai", "model": "gpt-image-1-mini", "style_prompt": ""}), \
             patch("app.services.image_service._get_openai", return_value=client):
            data, model, content_type = await generate_hero_image(SAMPLE_JOURNEYS[0])
        assert data == b"hello"
        assert model == "gpt-image-1-mini"
        assert content_type == "image/webp"
        kwargs = client.images.generate.call_args.kwargs
        assert kwargs["quality"] == "medium"
        assert kwargs["output_format"] == "webp"
        assert kwargs["size"] == "1024x1024"

    @pytest.mark.asyncio
    async def test_dalle_request_shape(self):
        fake_resp = MagicMock()
        fake_resp.data = [MagicMock(b64_json="aGVsbG8=")]
        client = MagicMock()
        client.images.generate = AsyncMock(return_value=fake_resp)
        with patch("app.services.image_service.get_config",
                   return_value={"provider": "openai", "model": "dall-e-3", "style_prompt": ""}), \
             patch("app.services.image_service._get_openai", return_value=client):
            _, _, content_type = await generate_hero_image(SAMPLE_JOURNEYS[0])
        assert content_type == "image/png"
        kwargs = client.images.generate.call_args.kwargs
        assert kwargs["response_format"] == "b64_json"
        assert "output_format" not in kwargs
