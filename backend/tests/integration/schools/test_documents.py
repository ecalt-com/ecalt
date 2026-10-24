"""Source-document upload/verify/list/delete (README §3.6, SC-301/SC-305).

Covers the validation gate on `upload-url`, the server-side verification on
`complete` (magic bytes, macros, sha256 dedupe) and the lifecycle endpoints.
Storage is the in-memory `fake_storage` fixture; no real bucket is touched.
"""
import io
import zipfile

import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def _url(w, *rest):
    return "/".join((f"/api/v1/schools/{w.school_a['id']}/documents", *rest)) if rest \
        else f"/api/v1/schools/{w.school_a['id']}/documents"


def _upload_url(client, w, **body):
    body = {"filename": "notes.pdf", "size_bytes": 2048, "mime": "application/pdf", **body}
    return client.post(_url(w, "upload-url"), json=body, headers=w.headers("SA"))


def test_upload_url_happy_path(client, world, db):
    r = _upload_url(client, world)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["document_id"] and body["upload_url"].startswith("https://")
    assert body["storage_path"].endswith(".pdf")
    rows = f.fetch(db, "SELECT status, filename, storage_path FROM source_documents WHERE id = %s",
                   (body["document_id"],))
    assert rows[0]["status"] == "pending_upload" and rows[0]["storage_path"] == body["storage_path"]


@pytest.mark.parametrize("filename,size,reason", [
    ("notes.doc", 2048, "legacy_word"),
    ("notes.docm", 2048, "legacy_word"),
    ("notes.txt", 2048, "unsupported_type"),
    ("notes.pdf", 0, "empty_file"),
    ("notes.pdf", 26 * 1024 * 1024, "too_large"),
])
def test_upload_url_rejects_bad_requests(client, world, filename, size, reason):
    r = _upload_url(client, world, filename=filename, size_bytes=size)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "document_rejected"
    assert r.json()["detail"]["reason"] == reason


def test_complete_verifies_and_enqueues_extract(client, world, db):
    doc_id = _upload_url(client, world).json()["document_id"]
    r = client.post(_url(world, doc_id, "complete"), headers=world.headers("SA"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "uploaded"
    # sha256 recorded, and an extract job was queued for the worker to pick up.
    assert f.fetch(db, "SELECT sha256 FROM source_documents WHERE id = %s", (doc_id,))[0]["sha256"]
    jobs = f.fetch(db, "SELECT kind, status, payload FROM school_jobs WHERE school_id = %s",
                   (world.school_a["id"],))
    assert jobs == [{"kind": "extract", "status": "queued", "payload": {"document_id": doc_id}}]


def test_complete_rejects_wrong_magic_bytes(client, world, fake_storage):
    up = _upload_url(client, world).json()
    fake_storage.put(up["storage_path"], b"this is not a pdf at all")
    r = client.post(_url(world, up["document_id"], "complete"), headers=world.headers("SA"))
    assert r.status_code == 422 and r.json()["detail"]["reason"] == "corrupt"


def test_complete_rejects_macro_docx(client, world, fake_storage):
    up = _upload_url(client, world, filename="lesson.docx",
                     mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document").json()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr("word/vbaProject.bin", b"\x00macro\x00")
    fake_storage.put(up["storage_path"], buf.getvalue())
    r = client.post(_url(world, up["document_id"], "complete"), headers=world.headers("SA"))
    assert r.status_code == 422 and r.json()["detail"]["reason"] == "macro"


def test_complete_deduplicates_within_school(client, world, db):
    first = _upload_url(client, world).json()["document_id"]
    second = _upload_url(client, world).json()["document_id"]
    client.post(_url(world, first, "complete"), headers=world.headers("SA"))
    # Same bytes (the canned PDF) → the second collapses onto the first.
    r = client.post(_url(world, second, "complete"), headers=world.headers("SA"))
    assert r.status_code == 200 and r.json()["id"] == first
    assert f.fetch(db, "SELECT status FROM source_documents WHERE id = %s", (second,))[0]["status"] == "deleted"


def test_list_get_and_delete(client, world, db):
    doc = f.make_document(db, world.school_a, filename="unit1.pdf")
    f.add_chunks(db, doc["id"], ["chunk one", "chunk two"])

    listed = client.get(_url(world), headers=world.headers("SA")).json()["documents"]
    assert [d["id"] for d in listed] == [doc["id"]]
    assert "storage_path" not in listed[0] and "sha256" not in listed[0]

    assert client.get(_url(world, doc["id"]), headers=world.headers("SA")).json()["filename"] == "unit1.pdf"

    assert client.delete(_url(world, doc["id"]), headers=world.headers("SA")).status_code == 204
    # Soft-deleted, chunks gone, and no longer returned or fetchable.
    assert f.fetch(db, "SELECT status FROM source_documents WHERE id = %s", (doc["id"],))[0]["status"] == "deleted"
    assert f.fetch(db, "SELECT count(*) AS n FROM document_chunks WHERE document_id = %s", (doc["id"],))[0]["n"] == 0
    assert client.get(_url(world, doc["id"]), headers=world.headers("SA")).status_code == 404
    assert client.get(_url(world), headers=world.headers("SA")).json()["documents"] == []


def test_storage_unavailable_returns_503(client, world, fake_storage):
    fake_storage.disable()
    r = _upload_url(client, world)
    assert r.status_code == 503 and r.json()["detail"]["error"] == "storage_unavailable"
