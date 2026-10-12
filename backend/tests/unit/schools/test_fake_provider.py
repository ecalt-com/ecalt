"""SC-006: the fake provider behaves as documented, so pipeline tests built on
it (M3/M4) can trust it."""
import asyncio

import pytest

from tests.fakes.fake_provider import FakeProvider


async def test_ok_mode_returns_registered_text_and_records_calls():
    fake = FakeProvider().respond("outline", '{"steps": []}')
    text, in_tok, out_tok, cached = await fake.complete_text("outline", "sys", "user text", max_tokens=99)
    assert text == '{"steps": []}' and in_tok > 0 and out_tok > 0 and cached == 0
    assert fake.call_count() == 1 and fake.calls_for("outline")[0].max_tokens == 99


async def test_callable_response_sees_the_prompt():
    fake = FakeProvider().respond("step", lambda system, user: user.upper())
    assert (await fake.complete_text("step", "s", "abc"))[0] == "ABC"


async def test_failure_modes():
    fake = FakeProvider().respond("outline", "ok")
    fake.set_mode("malformed_json", "outline")
    assert (await fake.complete_text("outline", "s", "u"))[0] == "{not json"
    fake.set_mode("timeout", "outline")
    with pytest.raises(asyncio.TimeoutError):
        await fake.complete_text("outline", "s", "u")
    fake.set_mode("exception", "outline")
    with pytest.raises(RuntimeError):
        await fake.complete_text("outline", "s", "u")
    fake.respond("outline", '{"bad": true}', mode="bad_chunk_ids").set_mode("bad_chunk_ids", "outline")
    assert (await fake.complete_text("outline", "s", "u"))[0] == '{"bad": true}'


async def test_unregistered_response_fails_loudly():
    with pytest.raises(AssertionError):
        await FakeProvider().complete_text("anything", "s", "u")


async def test_slow_mode_tracks_concurrency():
    fake = FakeProvider(slow_seconds=0.02).respond("step", "x").set_mode("slow")
    await asyncio.gather(*(fake.complete_text("step", "s", "u") for _ in range(5)))
    assert fake.max_in_flight == 5 and fake.in_flight == 0


async def test_install_patches_importing_modules(monkeypatch):
    from app.services import provider_service, spark_service
    fake = FakeProvider().install(monkeypatch)
    assert spark_service.complete_text == fake.complete_text
    assert provider_service.complete_text == fake.complete_text
