"""F2.2: the language instruction reaches learner-facing prompts only, and non-Latin questions are moderated."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import content_filter, language_service as ls, provider_service


def test_english_prompts_are_untouched():
    for t in ("journey", "step_content", "quiz", "content_critic", "visual_planner"):
        assert ls.apply("SYSTEM", t) == "SYSTEM"
    with ls.use_language("en"):
        assert ls.apply("SYSTEM", "journey") == "SYSTEM"


def test_hindi_is_appended_for_learner_facing_types_only():
    with ls.use_language("hi"):
        out = ls.apply("SYSTEM", "step_content")
        assert out.startswith("SYSTEM") and "Hindi" in out and "Devanagari" in out and "JSON keys" in out
        for t in ("content_critic", "visual_planner", "knowledge_extraction", "mind_signature", "nudge", None):
            assert ls.apply("SYSTEM", t) == "SYSTEM"
    assert ls.current() == "en"                      # restored afterwards


def test_unknown_codes_fall_back_to_english():
    assert ls.normalize("xx") == "en" and ls.normalize(None) == "en" and ls.normalize(" HI ") == "hi"
    with ls.use_language("klingon"):
        assert ls.current() == "en"


def test_context_is_visible_across_awaits_and_isolated_between_tasks():
    seen = {}

    async def worker(name, code):
        with ls.use_language(code):
            await asyncio.sleep(0.01)
            seen[name] = ls.current()

    async def main():
        await asyncio.gather(worker("a", "hi"), worker("b", "en"))
        return ls.current()

    assert asyncio.run(main()) == "en" and seen == {"a": "hi", "b": "en"}


def test_complete_text_adds_the_instruction_to_the_system_prompt(monkeypatch):
    captured = {}

    async def create(**kw):
        captured["messages"] = kw["messages"]
        return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, prompt_tokens_details=None),
                               choices=[SimpleNamespace(message=SimpleNamespace(content=" ok "))])

    client = MagicMock(); client.chat.completions.create = create
    monkeypatch.setattr(provider_service, "_get_openai", lambda: client)
    monkeypatch.setattr(provider_service, "get_config",
                        lambda t: {"provider": "openai", "model": "gpt-x", "style_prompt": ""})
    with ls.use_language("hi"):
        asyncio.run(provider_service.complete_text("step_content", "BASE", "hello"))
    assert captured["messages"][0]["content"].startswith("BASE") and "Hindi" in captured["messages"][0]["content"]
    asyncio.run(provider_service.complete_text("step_content", "BASE", "hello"))
    assert captured["messages"][0]["content"] == "BASE"


# ── moderation of non-Latin questions ────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("How do black holes work?", False), ("café déjà vu", False), ("", False), ("123 ???", False),
    ("ब्लैक होल कैसे काम करते हैं?", True), ("黑洞是如何形成的", True), ("mix of English और हिन्दी शब्द बहुत", True),
])
def test_is_mostly_non_latin(text, expected):
    assert content_filter.is_mostly_non_latin(text) is expected


def _moderation(monkeypatch, flagged=(), error=None):
    create = AsyncMock(side_effect=error) if error else AsyncMock(return_value=SimpleNamespace(
        results=[SimpleNamespace(categories=SimpleNamespace(**{c: True for c in flagged}))]))
    client = MagicMock(); client.moderations.create = create
    monkeypatch.setattr(provider_service, "_get_openai", lambda: client)
    monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "sk-test")
    return create


def test_english_questions_never_reach_the_moderation_api(monkeypatch):
    create = _moderation(monkeypatch)
    assert asyncio.run(content_filter.moderate_non_english("How does DNA work?")) == (True, "")
    create.assert_not_awaited()


def test_a_flagged_non_latin_question_is_refused(monkeypatch):
    _moderation(monkeypatch, flagged=("illicit",))
    allowed, message = asyncio.run(content_filter.moderate_non_english("कुछ खतरनाक निर्देश कैसे बनाएं"))
    assert allowed is False and message == content_filter._REFUSAL


def test_a_clean_non_latin_question_passes_and_moderation_fails_open(monkeypatch):
    _moderation(monkeypatch)
    assert asyncio.run(content_filter.moderate_non_english("ब्लैक होल क्या है?")) == (True, "")
    _moderation(monkeypatch, error=RuntimeError("moderation down"))
    assert asyncio.run(content_filter.moderate_non_english("ब्लैक होल क्या है?")) == (True, "")


def test_without_an_openai_key_nothing_is_called(monkeypatch):
    create = _moderation(monkeypatch)
    monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "")
    assert asyncio.run(content_filter.moderate_non_english("ब्लैक होल क्या है?")) == (True, "")
    create.assert_not_awaited()


def test_non_english_gets_a_larger_token_allowance_for_learner_facing_types_only():
    assert ls.scale_tokens(3000, "journey") == 3000
    with ls.use_language("hi"):
        assert ls.scale_tokens(3000, "journey") == 9000
        assert ls.scale_tokens(1024, "daily_chat") == 3072
        assert ls.scale_tokens(200, "content_critic") == 200      # not shown to anyone: unchanged
    assert ls.scale_tokens(3000, "journey") == 3000
