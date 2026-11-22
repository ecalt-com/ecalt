"""F1.4: signed click-through links."""
from urllib.parse import parse_qs, urlparse

import pytest

from app.services import notification_links as nl


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(nl.settings, "NOTIFICATION_SIGNING_SECRET", "test-secret")
    monkeypatch.setattr(nl.settings, "FRONTEND_URL", "https://app.example.com/")


def test_round_trip_and_tamper_detection():
    url = nl.build_click_url("log-1", "/journey/abc#step-s2")
    q = parse_qs(urlparse(url).query)
    assert urlparse(url).path == "/api/v1/notifications/c/log-1"
    assert nl.verify_click("log-1", q["to"][0], q["sig"][0])
    assert not nl.verify_click("log-2", q["to"][0], q["sig"][0])        # other row
    assert not nl.verify_click("log-1", "/learn", q["sig"][0])          # other target
    assert not nl.verify_click("log-1", q["to"][0], "")


@pytest.mark.parametrize("bad", ["https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)",
                                 "evil", "", "/a\nb", "/x:y", "/" + "a" * 400])
def test_unsafe_targets_are_rejected_even_when_signed(bad):
    assert not nl.is_safe_target(bad)
    assert not nl.verify_click("l", bad, nl.sign_click("l", bad))


@pytest.mark.parametrize("good", ["/learn", "/review", "/journey/abc#step-s1", "/journey/a?x=1"])
def test_safe_targets(good):
    assert nl.is_safe_target(good)


def test_landing_url_puts_utm_before_the_fragment():
    assert nl.landing_url("/journey/a#step-s2", "email", "journey_almost_done") == \
        "https://app.example.com/journey/a?utm_source=notif&utm_medium=email&utm_campaign=journey_almost_done#step-s2"
    assert "&utm_source=notif" in nl.landing_url("/x?y=1", "whatsapp", "daily_spark")


def test_target_paths():
    ctx = {"journey_id": "j 1", "next_step_id": "s2"}
    assert nl.target_path("journey_almost_done", ctx) == "/journey/j%201#step-s2"
    assert nl.target_path("journey_almost_done", {"journey_id": "j1"}) == "/journey/j1"
    assert nl.target_path("daily_spark", ctx) == "/learn"
    assert nl.target_path("review_due", {}) == "/review"
    assert nl.target_path("journey_almost_done", {}) == "/learn"


def test_attempt_send_swaps_the_plain_link_for_the_tracked_one(monkeypatch):
    import asyncio
    from app.services import copy_generator, email_service
    from app.services.notification_service import SENT, notification_service as svc

    plain = "https://app.example.com/journey/j1#step-s2"
    async def fake_copy(ntype, ctx, uid=None):
        return {"subject": "s", "body_html": f'<a href="{plain}">Go</a>', "short_message": f"hey {plain}",
                "target_path": "/journey/j1#step-s2"}
    sent = {}
    async def fake_email(**kw):
        sent.update(kw); return True
    async def yes(*a, **k): return True
    async def no(*a, **k): return False
    async def log(*a, **k): return "log-9"
    monkeypatch.setattr(copy_generator, "generate_copy", fake_copy)
    monkeypatch.setattr(email_service, "send_email", fake_email)
    monkeypatch.setattr(svc, "can_send", yes)
    monkeypatch.setattr(svc, "is_quiet_hours", no)
    monkeypatch.setattr(svc, "log_notification", log)
    monkeypatch.setattr("app.core.config.settings.NOTIFICATIONS_EMAIL_ENABLED", True, raising=False)

    out = asyncio.run(svc.attempt_send("u1", "u1@x.com", "journey_almost_done", "email",
                                       {"name": "A", "journey_id": "j1"}))
    assert out.status == SENT
    assert "/api/v1/notifications/c/log-9?to=" in sent["html_body"] and plain not in sent["html_body"]
    assert "/api/v1/notifications/c/log-9?to=" in sent["text_body"]
