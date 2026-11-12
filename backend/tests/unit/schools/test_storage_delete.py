"""Supabase Storage reports a missing object as HTTP 400 with statusCode "404"
in the body. Deletes must treat that as already gone, or a retried offboarding
run would fail forever on files an earlier run removed (SC-803)."""
import httpx
import pytest

from app.services import image_service
from app.services import school_storage_service as storage


def _resp(status, body):
    return httpx.Response(status, json=body, request=httpx.Request("DELETE", "https://x.invalid"))


@pytest.mark.parametrize("status,body,missing", [
    (404, {}, True),
    (400, {"statusCode": "404", "error": "not_found", "code": "NoSuchKey"}, True),
    (400, {"statusCode": "404", "error": "Bucket not found", "code": "NoSuchBucket"}, True),
    (400, {"statusCode": "400", "error": "InvalidKey"}, False),
    (200, {}, False),
    (500, {}, False),
])
def test_object_missing(status, body, missing):
    assert storage.object_missing(_resp(status, body)) is missing


class _Client:
    def __init__(self, resp):
        self.resp = resp
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def delete(self, url, headers=None):
        return self.resp


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(storage.settings, "SUPABASE_SERVICE_ROLE_KEY", "k")


def test_strict_delete_ignores_missing_and_raises_on_errors(configured, monkeypatch):
    monkeypatch.setattr(storage.httpx, "Client", lambda timeout=None: _Client(_resp(400, {"statusCode": "404"})))
    storage.delete("a/b.pdf", strict=True)
    monkeypatch.setattr(storage.httpx, "Client", lambda timeout=None: _Client(_resp(500, {})))
    with pytest.raises(storage.StorageError):
        storage.delete("a/b.pdf", strict=True)
    storage.delete("a/b.pdf")  # non-strict only logs


def test_hero_delete_only_touches_our_bucket(configured, monkeypatch):
    calls = []
    monkeypatch.setattr(image_service.settings, "SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(image_service.httpx, "delete",
                        lambda url, **kw: calls.append(url) or _resp(400, {"statusCode": "404"}))
    assert image_service.delete_journey_image("https://images.example.com/x.webp") is False
    assert image_service.delete_journey_image(
        "https://proj.supabase.co/storage/v1/object/public/journey-images/j1.webp") is True
    assert calls == ["https://proj.supabase.co/storage/v1/object/journey-images/j1.webp"]
    monkeypatch.setattr(image_service.httpx, "delete", lambda url, **kw: _resp(500, {}))
    with pytest.raises(httpx.HTTPStatusError):
        image_service.delete_journey_image("https://proj.supabase.co/storage/v1/object/public/journey-images/j1.webp")
