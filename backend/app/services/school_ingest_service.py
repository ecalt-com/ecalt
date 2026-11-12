"""Document extraction job (M3 SC-303/304).

The `extract` job handler: download the uploaded original, parse it in the
sandboxed `school_extract_worker` subprocess (wall-clock timeout + address-space
cap), chunk the result into `document_chunks`, and move the document to its final
status — `ready`, `needs_ocr` (scanned/garbled, awaiting M3b), or `failed`.
Registered with the job queue at import.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Optional

import psycopg2.extras

from app.core.config import settings
from app.core.database import get_db
from app.services import doc_parsing, school_jobs
from app.services import school_storage_service as storage

logger = logging.getLogger(__name__)

_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_extract_worker.py")
_EXT = {doc_parsing.PDF_MIME: "pdf", doc_parsing.DOCX_MIME: "docx"}


def _limit_memory():  # pragma: no cover - runs only in the child process
    """preexec_fn: cap the child's address space so a zip bomb can't OOM us.
    Linux only — on macOS RLIMIT_AS counts reserved virtual memory and can kill
    the interpreter at startup, so there the wall-clock timeout is the guard."""
    try:
        if not sys.platform.startswith("linux"):
            return
        import resource
        cap = settings.SCHOOL_DOC_EXTRACT_MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    except Exception:
        pass  # best-effort; the wall-clock timeout is the hard guard


def _run_sandbox(path: str, mime: str, max_pages: int) -> dict:
    """Parse a file in an isolated subprocess. Raises on timeout or a crash so
    the job records a failure (and retries)."""
    proc = subprocess.run(
        [sys.executable, _WORKER, path, mime, str(max_pages)],
        capture_output=True, text=True,
        timeout=settings.SCHOOL_DOC_EXTRACT_TIMEOUT_SECONDS,
        preexec_fn=_limit_memory if os.name == "posix" else None,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"extractor failed (exit {proc.returncode}): {proc.stderr[:300]}")
    return json.loads(proc.stdout)


def extract_handler(job: dict) -> dict:
    document_id = job["payload"].get("document_id")
    if not document_id:
        raise ValueError("extract job missing document_id")
    doc = _load(job["school_id"], document_id)
    if not doc:
        return {"status": "skipped", "reason": "document gone"}
    if doc["status"] == "deleted":
        return {"status": "skipped", "reason": "deleted"}

    _set_status(document_id, "extracting")
    # Parse exactly the bytes `complete` verified: the signed upload URL allows
    # overwrites, so a file swapped in after verification is refused here.
    try:
        data = storage.download(doc["storage_path"],
                                max_bytes=settings.SCHOOL_DOC_MAX_MB * 1024 * 1024)
    except storage.ObjectTooLarge:
        _set_status(document_id, "failed", error_code="changed_after_upload")
        return {"status": "failed", "error_code": "changed_after_upload"}
    if doc.get("sha256") and hashlib.sha256(data).hexdigest() != doc["sha256"]:
        _set_status(document_id, "failed", error_code="changed_after_upload")
        return {"status": "failed", "error_code": "changed_after_upload"}
    ext = _EXT.get(doc["mime"], "bin")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f"source.{ext}")
        with open(path, "wb") as f:
            f.write(data)
        try:
            parsed = _run_sandbox(path, doc["mime"], settings.SCHOOL_DOC_MAX_PAGES)
        except subprocess.TimeoutExpired:
            _set_status(document_id, "failed", error_code="extract_timeout")
            return {"status": "failed", "error_code": "extract_timeout"}

    if not parsed.get("ok"):
        code = parsed.get("error_code", "extract_failed")
        _set_status(document_id, "failed", error_code=code)
        return {"status": "failed", "error_code": code}

    quality = parsed.get("quality") or {}
    page_count = parsed.get("page_count")
    if quality.get("scanned") or quality.get("garbled"):
        # Text-bearing extraction didn't work; OCR (M3b) is the path forward.
        _set_status(document_id, "needs_ocr", page_count=page_count,
                    error_code="scanned" if quality.get("scanned") else "garbled")
        return {"status": "needs_ocr"}

    chunks = doc_parsing.chunk_blocks(
        parsed["blocks"], max_chars=settings.SCHOOL_DOC_MAX_CHARS,
    )
    if not chunks:
        _set_status(document_id, "needs_ocr", page_count=page_count, error_code="no_text")
        return {"status": "needs_ocr"}

    _write_chunks(document_id, chunks)
    _set_status(document_id, "ready", page_count=page_count, language=parsed.get("language"),
                error_code=None)
    logger.info("extracted document %s: %s chunks, %s pages", document_id, len(chunks), page_count)
    return {"status": "ready", "chunks": len(chunks), "page_count": page_count}


# ── DB helpers ───────────────────────────────────────────────────────────────

def _load(school_id: str, document_id: str) -> Optional[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, school_id, mime, storage_path, status, sha256 FROM source_documents WHERE id = %s AND school_id = %s",
                (document_id, school_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _set_status(document_id: str, status: str, *, page_count=None, language=None, error_code="__keep__") -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE source_documents
                   SET status = %s,
                       page_count = COALESCE(%s, page_count),
                       language = COALESCE(%s, language),
                       error_code = CASE WHEN %s = '__keep__' THEN error_code ELSE %s END,
                       updated_at = now()
                 WHERE id = %s
                """,
                (status, page_count, language, error_code, error_code, document_id),
            )


def _write_chunks(document_id: str, chunks: list) -> None:
    """Replace the document's chunks (idempotent across job retries)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (document_id,))
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO document_chunks
                    (document_id, ordinal, heading_path, page_start, page_end, text, char_count)
                VALUES %s
                """,
                [(document_id, c["ordinal"], c["heading_path"], c["page_start"],
                  c["page_end"], c["text"], c["char_count"]) for c in chunks],
                template="(%s, %s, %s, %s, %s, %s, %s)",
            )


school_jobs.register_handler("extract", extract_handler)
