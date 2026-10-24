"""Sandboxed document-extraction worker (M3 SC-303).

Run as a short-lived subprocess by `school_ingest_service` with a wall-clock
timeout and an address-space cap, so a hostile or pathological document can
neither hang nor OOM the job worker. It reads one file and prints the parse
result as JSON on stdout; it imports only `doc_parsing` plus the PDF/Word
libraries — never the app, DB, or network.

    python school_extract_worker.py <file_path> <mime> <max_pages>
"""
import json
import os
import sys

# Make the sibling `doc_parsing` importable without pulling in the `app` package
# (this process is deliberately isolated from the application).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import doc_parsing  # noqa: E402


def main() -> int:
    try:
        path, mime, max_pages = sys.argv[1], sys.argv[2], int(sys.argv[3])
    except (IndexError, ValueError):
        sys.stderr.write("usage: school_extract_worker.py <file_path> <mime> <max_pages>\n")
        return 2
    try:
        with open(path, "rb") as f:
            data = f.read()
        result = doc_parsing.parse(data, mime, max_pages=max_pages)
    except MemoryError:
        result = {"ok": False, "error_code": "too_large"}
    except Exception as exc:  # never crash — report a failure the parent can store
        result = {"ok": False, "error_code": "extract_failed", "detail": str(exc)[:200]}
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
