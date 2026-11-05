"""SC-009 / #19: rate limits key on the real client, measured on Railway dev."""
import pytest
from starlette.requests import Request

from app.core import limiter


def _req(headers: dict, host="100.64.0.2"):
    scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
             "client": (host, 1234)}
    return Request(scope)


def test_direct_call_uses_railway_real_ip_not_the_proxy():
    r = _req({"x-real-ip": "49.42.195.167", "x-forwarded-for": "49.42.195.167, 152.233.15.121"})
    assert limiter.client_ip(r) == "49.42.195.167"


def test_spa_call_via_vercel_uses_the_browser_ip():
    r = _req({"x-real-ip": "13.126.34.128", "x-vercel-forwarded-for": "49.42.195.167",
              "x-vercel-proxy-signature": "Bearer abc"})
    assert limiter.client_ip(r) == "49.42.195.167"


def test_vercel_header_without_signature_is_ignored():
    r = _req({"x-real-ip": "49.42.195.167", "x-vercel-forwarded-for": "8.8.8.8"})
    assert limiter.client_ip(r) == "49.42.195.167"


def test_trust_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(limiter.settings, "RATE_LIMIT_TRUST_VERCEL_HEADER", False)
    r = _req({"x-real-ip": "13.126.34.128", "x-vercel-forwarded-for": "49.42.195.167",
              "x-vercel-proxy-signature": "Bearer abc"})
    assert limiter.client_ip(r) == "13.126.34.128"


@pytest.mark.parametrize("bad", ["", "not-an-ip", "1.2.3.4.5", "<script>"])
def test_garbage_headers_fall_back(bad):
    r = _req({"x-real-ip": bad, "x-vercel-forwarded-for": bad, "x-vercel-proxy-signature": "x"}, host="127.0.0.1")
    assert limiter.client_ip(r) == "127.0.0.1"
