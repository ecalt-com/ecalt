"""Pure document parsing + chunking for school course ingestion (M3 SC-303/304).

**No app or DB imports** — this module runs inside the sandboxed extraction
subprocess (`school_extract_worker`) and is unit-tested directly. It turns PDF or
Word bytes into an ordered list of text *blocks* (text + heading context + page
range), flags scanned or garbled documents for OCR, and chunks the blocks into
roughly section-sized pieces for the course builder.

A *block* is ``{"text", "heading_path": [str], "page_start": int|None, "page_end": int|None}``.
A *chunk* adds ``{"ordinal", "char_count"}`` and drops short repeated headers/footers.
"""
from __future__ import annotations

import io
import zipfile
from collections import Counter
from typing import Optional

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Zip-bomb / XXE guards for DOCX (a .docx is a ZIP of XML).
_DOCX_MAX_UNCOMPRESSED = 100 * 1024 * 1024
_DOCX_MAX_ENTRIES = 5000
# A page with less than this many characters of extracted text is "near-empty"
# (likely a scanned image). >30% near-empty pages ⇒ the document needs OCR.
_NEAR_EMPTY_CHARS = 20
_SCANNED_RATIO = 0.30
# Share of "sensible" characters below which the text is treated as garbled
# (broken font encodings, e.g. mis-mapped Devanagari) and routed to OCR.
_GARBLED_FLOOR = 0.6


def parse(data: bytes, mime: str, *, max_pages: int) -> dict:
    """Parse a document to ``{ok, blocks, page_count, language, quality}`` or,
    on a rejection, ``{ok: False, error_code}``. Dispatches on content first
    (magic bytes), falling back to the declared mime."""
    if data[:5] == b"%PDF-" or mime == PDF_MIME:
        return parse_pdf(data, max_pages=max_pages)
    if data[:4] == b"PK\x03\x04" or mime == DOCX_MIME:
        return parse_docx(data)
    return {"ok": False, "error_code": "unsupported_type"}


# ── PDF ──────────────────────────────────────────────────────────────────────

def parse_pdf(data: bytes, *, max_pages: int) -> dict:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            return {"ok": False, "error_code": "encrypted"}
        page_count = len(reader.pages)
    except Exception:
        return {"ok": False, "error_code": "unreadable"}

    if page_count == 0:
        return {"ok": False, "error_code": "empty"}
    if page_count > max_pages:
        return {"ok": False, "error_code": "too_many_pages"}

    blocks: list[dict] = []
    near_empty = 0
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        if len(text) < _NEAR_EMPTY_CHARS:
            near_empty += 1
        if text:
            blocks.append({"text": text, "heading_path": [], "page_start": i, "page_end": i})

    scanned = (near_empty / page_count) > _SCANNED_RATIO
    joined = "\n".join(b["text"] for b in blocks)
    garbled = (not joined) or _sensible_ratio(joined) < _GARBLED_FLOOR
    return {
        "ok": True,
        "blocks": blocks,
        "page_count": page_count,
        "language": None,
        "quality": {"scanned": scanned, "garbled": garbled, "near_empty_pages": near_empty},
    }


# ── DOCX ─────────────────────────────────────────────────────────────────────

def parse_docx(data: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > _DOCX_MAX_ENTRIES or sum(zi.file_size for zi in infos) > _DOCX_MAX_UNCOMPRESSED:
                return {"ok": False, "error_code": "too_large"}
            if any(n.endswith("vbaProject.bin") for n in zf.namelist()):
                return {"ok": False, "error_code": "macro"}
    except zipfile.BadZipFile:
        return {"ok": False, "error_code": "unreadable"}

    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = Document(io.BytesIO(data))
    except Exception:
        return {"ok": False, "error_code": "unreadable"}

    blocks: list[dict] = []
    heading_stack: list[tuple[int, str]] = []  # (level, text)

    def path() -> list:
        return [t for (_, t) in heading_stack]

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            para = Paragraph(child, doc)
            text = para.text.strip()
            style = (para.style.name if para.style else "") or ""
            if style.startswith("Heading"):
                last = style.split()[-1]
                level = int(last) if last.isdigit() else 1
                heading_stack[:] = [(l, t) for (l, t) in heading_stack if l < level]
                if text:
                    heading_stack.append((level, text))
            elif text:
                blocks.append({"text": text, "heading_path": path(), "page_start": None, "page_end": None})
        elif child.tag == qn("w:tbl"):
            md = _table_to_markdown(Table(child, doc))
            if md:
                blocks.append({"text": md, "heading_path": path(), "page_start": None, "page_end": None})

    joined = "\n".join(b["text"] for b in blocks)
    garbled = (not joined) or _sensible_ratio(joined) < _GARBLED_FLOOR
    return {
        "ok": True,
        "blocks": blocks,
        "page_count": None,
        "language": None,
        "quality": {"scanned": False, "garbled": garbled, "near_empty_pages": 0},
    }


def _table_to_markdown(table) -> str:
    rows = []
    for row in table.rows:
        cells = [(" ".join(c.text.split())) for c in row.cells]
        if any(cells):
            rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    if len(rows) > 1:  # header separator after the first row
        cols = rows[0].count("|") - 1
        rows.insert(1, "| " + " | ".join(["---"] * cols) + " |")
    return "\n".join(rows)


# ── Quality + chunking ───────────────────────────────────────────────────────

_SENSIBLE_PUNCT = set(" .,;:!?'\"()[]{}-–—/%&@#\n\t*|+=°₹$")


def _sensible_ratio(text: str) -> float:
    """Fraction of characters that are letters/digits (any script) or ordinary
    punctuation. Broken encodings pile up private-use or symbol glyphs, which
    drags this well below 1.0."""
    if not text:
        return 0.0
    good = sum(1 for c in text if c.isalnum() or c in _SENSIBLE_PUNCT)
    return good / len(text)


def chunk_blocks(blocks: list, *, max_chars: int, target_chars: int = 8000) -> list:
    """Group blocks into chunks that respect section boundaries (a change of
    ``heading_path`` starts a new chunk) and stay near ``target_chars`` (~2k
    tokens). Repeated headers/footers are stripped first, and the total is
    capped at ``max_chars``."""
    blocks = _strip_repeated_lines(blocks)
    chunks: list[dict] = []
    buf: list[str] = []
    path: Optional[list] = None
    p_start: Optional[int] = None
    p_end: Optional[int] = None
    buf_len = 0
    total = 0

    def flush():
        nonlocal buf, buf_len, path, p_start, p_end
        text = "\n\n".join(buf).strip()
        if text:
            chunks.append({
                "ordinal": len(chunks), "heading_path": path or [],
                "page_start": p_start, "page_end": p_end,
                "text": text, "char_count": len(text),
            })
        buf, buf_len, path, p_start, p_end = [], 0, None, None, None

    for b in blocks:
        if total >= max_chars:
            break
        if buf and (b["heading_path"] != path or buf_len + len(b["text"]) > target_chars):
            flush()
        if path is None:
            path = b["heading_path"]
        buf.append(b["text"])
        buf_len += len(b["text"])
        total += len(b["text"])
        if b.get("page_start") is not None:
            p_start = b["page_start"] if p_start is None else min(p_start, b["page_start"])
            p_end = b["page_end"] if p_end is None else max(p_end, b["page_end"])
    flush()
    return chunks


def _strip_repeated_lines(blocks: list) -> list:
    """Drop short lines that recur on most pages — running headers and footers.
    Only applies to paged (PDF) blocks; flow documents are left untouched."""
    paged = [b for b in blocks if b.get("page_start") is not None]
    if len(paged) < 4:
        return blocks
    freq: Counter = Counter()
    for b in paged:
        for ln in {l.strip() for l in b["text"].splitlines() if l.strip() and len(l.strip()) < 80}:
            freq[ln] += 1
    repeated = {ln for ln, c in freq.items() if c > len(paged) * 0.5}
    if not repeated:
        return blocks
    out = []
    for b in blocks:
        if b.get("page_start") is None:
            out.append(b)
            continue
        kept = "\n".join(l for l in b["text"].splitlines() if l.strip() not in repeated).strip()
        if kept:
            out.append({**b, "text": kept})
    return out
