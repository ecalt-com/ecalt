"""Deterministic stand-in for provider_service.complete_text (SC-006, TESTING.md §7.1).

    fake = FakeProvider()
    fake.respond("school_course_outline", '{"steps": [...]}')
    fake.install(monkeypatch)            # patches every app module that imported complete_text
    ...
    assert fake.call_count("school_step_content") == 4
    assert "<document>" in fake.calls[0].user_content

Modes (globally or per interaction type):
  ok              the registered response (text, or a callable(system, user_content) -> text)
  malformed_json  "{not json" — exercises retry / visible failure paths
  timeout         raises asyncio.TimeoutError
  exception       raises RuntimeError
  slow            sleeps `slow_seconds`, then behaves like ok (concurrency, cancellation)
  <any other>     a response registered for that mode, e.g. respond(t, text, mode="bad_chunk_ids")
"""
import asyncio
import sys
from dataclasses import dataclass
from typing import Callable, Optional, Union

Response = Union[str, Callable[[str, str], str]]


@dataclass
class Call:
    interaction_type: str
    system: str
    user_content: str
    max_tokens: int


class FakeProvider:
    def __init__(self, slow_seconds: float = 0.05):
        self.slow_seconds = slow_seconds
        self.calls: list[Call] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self._responses: dict[tuple[str, str], Response] = {}
        self._modes: dict[Optional[str], str] = {None: "ok"}

    # ── configuration ──
    def respond(self, interaction_type: str, response: Response, mode: str = "ok") -> "FakeProvider":
        self._responses[(interaction_type, mode)] = response
        return self

    def set_mode(self, mode: str, interaction_type: Optional[str] = None) -> "FakeProvider":
        self._modes[interaction_type] = mode
        return self

    # ── inspection ──
    def call_count(self, interaction_type: Optional[str] = None) -> int:
        return sum(1 for c in self.calls if interaction_type in (None, c.interaction_type))

    def calls_for(self, interaction_type: str) -> list[Call]:
        return [c for c in self.calls if c.interaction_type == interaction_type]

    # ── the fake itself ──
    def _text(self, interaction_type: str, mode: str, system: str, user_content: str) -> str:
        response = self._responses.get((interaction_type, mode))
        if response is None:
            raise AssertionError(f"FakeProvider: no '{mode}' response registered for {interaction_type!r}")
        return response(system, user_content) if callable(response) else response

    async def complete_text(self, interaction_type: str, system: str, user_content: str,
                            max_tokens: int = 1024) -> tuple[str, int, int, int]:
        self.calls.append(Call(interaction_type, system, user_content, max_tokens))
        mode = self._modes.get(interaction_type, self._modes[None])
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if mode == "timeout":
                raise asyncio.TimeoutError("fake provider timeout")
            if mode == "exception":
                raise RuntimeError("fake provider failure")
            if mode == "malformed_json":
                text = "{not json"
            elif mode == "slow":
                await asyncio.sleep(self.slow_seconds)
                text = self._text(interaction_type, "ok", system, user_content)
            else:
                text = self._text(interaction_type, mode, system, user_content)
        finally:
            self.in_flight -= 1
        return text, max(1, (len(system) + len(user_content)) // 4), max(1, len(text) // 4), 0

    def install(self, monkeypatch) -> "FakeProvider":
        """Replace complete_text in provider_service and in every app module
        that imported it by name."""
        from app.services import provider_service
        original = provider_service.complete_text
        for name, module in list(sys.modules.items()):
            if name.startswith("app.") and getattr(module, "complete_text", None) is original:
                monkeypatch.setattr(module, "complete_text", self.complete_text)
        return self
