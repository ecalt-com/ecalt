"""F1.6: link preview cards for crawlers."""
from unittest.mock import patch

import pytest

from app.api.v1.endpoints import share


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    monkeypatch.setattr(share, "frontend_url", lambda: "https://app.example.com")


def test_card_has_the_journey_title_image_and_canonical_url():
    row = {"title": "How black holes work", "description": "From stars to singularities",
           "hero_image_url": "https://img.example.com/h.png", "school_id": None, "profile_type": "account"}
    out = share.render_card("abc-1", row)
    assert '<meta property="og:title" content="How black holes work — ECALT">' in out
    assert 'content="https://img.example.com/h.png"' in out
    assert 'og:url" content="https://app.example.com/journey/abc-1"' in out
    assert 'twitter:card" content="summary_large_image"' in out


def test_user_text_is_escaped():
    row = {"title": '"><script>alert(1)</script>', "description": "<b>x</b> & y", "hero_image_url": None}
    out = share.render_card("abc", row)
    assert "<script>" not in out and "&lt;script&gt;" in out and "&amp; y" in out
    assert "https://app.example.com/og-image.png" in out


def test_missing_non_https_and_generic_rows_use_the_site_card():
    for row in (None, {"generic": True},
                {"title": "T", "description": "d", "hero_image_url": "javascript:alert(1)"}):
        out = share.render_card("abc", row)
        assert "javascript:" not in out and "https://app.example.com/og-image.png" in out
    assert "Turn Curiosity Into Capability" in share.render_card("abc", None)
    assert "Turn Curiosity Into Capability" in share.render_card("abc", {"generic": True})


def test_odd_ids_never_reach_the_page_or_database():
    assert share._lookup("../../etc/passwd") is None
    assert 'href="https://app.example.com"' in share.render_card("../x", None)


def test_endpoint_returns_html_and_survives_a_database_error(client):
    with patch.object(share, "_lookup", side_effect=RuntimeError("db down")):
        r = client.get("/api/v1/share/journey/abc")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "Turn Curiosity Into Capability" in r.text and r.headers["cache-control"] == "public, max-age=3600"
