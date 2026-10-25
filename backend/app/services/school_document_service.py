"""Source-document ingestion for school courses (README §3.6, SC-301/SC-305).

Flow: a teacher asks for an upload URL → the browser uploads straight to the
private bucket → the teacher calls `complete`, which downloads the object,
verifies it (size, magic bytes, no macros, sha256 dedupe within the school) and
enqueues an `extract` job. List/get/delete round it out. The heavy parsing lives
in the extract job (`school_ingest_service`), not here.
"""
from __future__ import annotations

import hashlib
import io
import logging
import zipfile
from typing import Optional

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_db
from app.core.school_auth import SchoolCtx, uuid_or_404
from app.services import school_jobs, school_storage_service as storage
from app.services.school_service import school_audit

logger = logging.getLogger(__name__)

# Only text-bearing formats we can parse in v1. `.doc`/`.docm` are refused with a
# "save as .docx or PDF" message; macros (`.docm`, embedded vbaProject) are a
# security risk and never accepted.
_EXT_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_PUBLIC_FIELDS = (
    "id, filename, mime, size_bytes, page_count, language, status, error_code, "
    "created_at, updated_at"
)


def _rejected(reason: str, message: str, status_code: int = 422) -> HTTPException:
    return HTTPException(status_code=status_code, detail={
        "error": "document_rejected", "reason": reason, "message": message,
    })


def _max_bytes() -> int:
    return settings.SCHOOL_DOC_MAX_MB * 1024 * 1024


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _storage_enabled_or_503() -> None:
    if not storage.storage_enabled():
        raise HTTPException(status_code=503, detail={
            "error": "storage_unavailable",
            "message": "Document storage isn't configured yet. Contact ECALT support.",
        })


# ── Upload / complete ────────────────────────────────────────────────────────

def create_upload(ctx: SchoolCtx, filename: str, size_bytes: int, mime: str) -> dict:
    """Validate the request, create a `pending_upload` row and return a signed
    URL the browser uploads the file to directly."""
    _storage_enabled_or_503()
    filename = (filename or "").strip()
    if not filename:
        raise _rejected("filename_required", "A file name is required.")
    ext = _ext(filename)
    if ext in ("doc", "docm"):
        raise _rejected("legacy_word", "Please save this as a .docx file or a PDF and upload again.")
    if ext not in _EXT_MIME:
        raise _rejected("unsupported_type", "Only PDF and Word (.docx) files are supported.")
    if size_bytes <= 0:
        raise _rejected("empty_file", "This file looks empty.")
    if size_bytes > _max_bytes():
        raise _rejected("too_large", f"Files must be {settings.SCHOOL_DOC_MAX_MB} MB or smaller.")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_documents (school_id, uploaded_by, filename, mime, size_bytes, status)
                VALUES (%s, %s, %s, %s, %s, 'pending_upload')
                RETURNING id
                """,
                (ctx.school_id, ctx.uid, filename, _EXT_MIME[ext], size_bytes),
            )
            document_id = str(cur.fetchone()["id"])
            object_path = f"{ctx.school_id}/{document_id}.{ext}"
            cur.execute(
                "UPDATE source_documents SET storage_path = %s WHERE id = %s",
                (object_path, document_id),
            )
            school_audit(cur, ctx.school_id, ctx.uid, "document.upload_started", "document", document_id,
                         {"ext": ext, "size_bytes": size_bytes})

    signed = storage.signed_upload_url(object_path)
    return {
        "document_id": document_id,
        "upload_url": signed["upload_url"],
        "token": signed["token"],
        "storage_path": object_path,
        "max_bytes": _max_bytes(),
    }


def _looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _check_docx(data: bytes) -> None:
    """A .docx is a ZIP with `word/document.xml`. Reject anything that isn't,
    and reject macro-enabled archives (`vbaProject.bin`)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        raise _rejected("corrupt", "This file isn't a valid Word document.")
    if "word/document.xml" not in names:
        raise _rejected("corrupt", "This file isn't a valid Word document.")
    if any(n.endswith("vbaProject.bin") for n in names):
        raise _rejected("macro", "Macro-enabled documents aren't allowed. Remove macros and re-upload.")


def complete(ctx: SchoolCtx, document_id: str) -> dict:
    """Verify the uploaded object and enqueue extraction. Idempotent within
    reason: a duplicate (same sha256 in the school) collapses onto the original."""
    _storage_enabled_or_503()
    document_id = uuid_or_404(document_id, "document_not_found")
    doc = _load(ctx.school_id, document_id)
    if doc["status"] not in ("pending_upload", "uploaded"):
        return _view(doc)  # already processed — nothing to do

    try:
        data = storage.download(doc["storage_path"], max_bytes=_max_bytes())
    except storage.ObjectTooLarge:
        raise _rejected("too_large", f"Files must be {settings.SCHOOL_DOC_MAX_MB} MB or smaller.")
    except storage.StorageError:
        raise _rejected("upload_missing", "We couldn't find the uploaded file. Please try the upload again.", 409)

    if len(data) == 0:
        raise _rejected("empty_file", "The uploaded file is empty.")
    if len(data) > _max_bytes():
        raise _rejected("too_large", f"Files must be {settings.SCHOOL_DOC_MAX_MB} MB or smaller.")

    ext = _ext(doc["filename"])
    if ext == "pdf":
        if not _looks_like_pdf(data):
            raise _rejected("corrupt", "This file isn't a valid PDF.")
    else:
        _check_docx(data)

    sha = hashlib.sha256(data).hexdigest()
    existing = _find_duplicate(ctx.school_id, sha, document_id)
    if existing:
        # Same bytes already uploaded: drop this object + row, point at the original.
        storage.delete(doc["storage_path"])
        _soft_delete(ctx.school_id, document_id, actor=ctx.uid, reason="duplicate")
        return _view(_load(ctx.school_id, existing))

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE source_documents
                   SET sha256 = %s, size_bytes = %s, status = 'uploaded', error_code = NULL,
                       updated_at = now()
                 WHERE id = %s AND school_id = %s
                """,
                (sha, len(data), document_id, ctx.school_id),
            )
            school_audit(cur, ctx.school_id, ctx.uid, "document.uploaded", "document", document_id)

    school_jobs.enqueue(ctx.school_id, "extract", {"document_id": document_id}, created_by=ctx.uid)
    return _view(_load(ctx.school_id, document_id))


# ── List / get / delete ──────────────────────────────────────────────────────

def list_documents(ctx: SchoolCtx) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {_PUBLIC_FIELDS} FROM source_documents
                    WHERE school_id = %s AND status <> 'deleted'
                    ORDER BY created_at DESC""",
                (ctx.school_id,),
            )
            return [_view(dict(r)) for r in cur.fetchall()]


def get_document(ctx: SchoolCtx, document_id: str) -> dict:
    document_id = uuid_or_404(document_id, "document_not_found")
    return _view(_load(ctx.school_id, document_id))


def delete_document(ctx: SchoolCtx, document_id: str) -> None:
    """Soft-delete: drop the storage object and chunks, keep the row (and any
    course_sources link) so published courses are unaffected (README §3.6)."""
    document_id = uuid_or_404(document_id, "document_not_found")
    doc = _load(ctx.school_id, document_id)
    if doc["storage_path"]:
        storage.delete(doc["storage_path"])
    _soft_delete(ctx.school_id, document_id, actor=ctx.uid, reason="deleted")


# ── Internals ────────────────────────────────────────────────────────────────

def _load(school_id: str, document_id: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM source_documents WHERE id = %s AND school_id = %s",
                (document_id, school_id),
            )
            row = cur.fetchone()
    if not row or row["status"] == "deleted":
        raise HTTPException(status_code=404, detail={
            "error": "document_not_found", "message": "Document not found."})
    return dict(row)


def _find_duplicate(school_id: str, sha: str, exclude_id: str) -> Optional[str]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM source_documents
                   WHERE school_id = %s AND sha256 = %s AND status <> 'deleted' AND id <> %s
                   LIMIT 1""",
                (school_id, sha, exclude_id),
            )
            row = cur.fetchone()
    return str(row["id"]) if row else None


def _soft_delete(school_id: str, document_id: str, *, actor: Optional[str], reason: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (document_id,))
            cur.execute(
                """UPDATE source_documents
                      SET status = 'deleted', deleted_at = now(), updated_at = now()
                    WHERE id = %s AND school_id = %s""",
                (document_id, school_id),
            )
            school_audit(cur, school_id, actor, "document.deleted", "document", document_id, {"reason": reason})


def _view(doc: dict) -> dict:
    """API-safe projection — never leaks `storage_path`, `sha256` or the raw
    uploader uid beyond what staff already see."""
    return {
        "id": str(doc["id"]),
        "filename": doc["filename"],
        "mime": doc["mime"],
        "size_bytes": doc["size_bytes"],
        "page_count": doc.get("page_count"),
        "language": doc.get("language"),
        "status": doc["status"],
        "error_code": doc.get("error_code"),
        "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else None,
    }
