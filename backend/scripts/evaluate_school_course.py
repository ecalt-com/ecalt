#!/usr/bin/env python
"""Eval harness for the AI course builder (plans/school-courses SC-411, gate G4).

Runs the grounded-generation pipeline over a fixture corpus and scores the
guarantees M4 depends on, then checks them against release thresholds and exits
non-zero if any fails. Run it on every prompt or model change.

    python scripts/evaluate_school_course.py              # offline (deterministic oracle)
    python scripts/evaluate_school_course.py --live        # call the real provider ($$)
    python scripts/evaluate_school_course.py --corpus path/to/dir

Metrics (per case, averaged):
  outline_grounding    every outline step cites ≥1 real chunk (schema contract)
  coverage             every top-level section is covered or explicitly skipped
  body_grounding       every step body cites only chunks the step was built on
  injection_resistance scripts / HTML / links in model output never survive into
                       stored content (SC-408)

Offline mode uses each corpus case's `oracle` responses, so it exercises the
validation + hardening (not the model's judgment); `--live` sends the real
prompts to the configured provider and scores its actual output.
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import sys

# Import the real builder internals — the harness scores the exact code path
# production uses (prompts, schema validation, sanitization).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import school_course_builder as b  # noqa: E402

_CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_eval_corpus")

# Release thresholds (gate G4).
THRESHOLDS = {
    "outline_grounding": 1.0,
    "coverage": 1.0,
    "body_grounding": 1.0,
    "injection_resistance": 1.0,
}

_UNSAFE_MARKERS = ("<script", "</script", "<b>", "<a ", "href=", "javascript:",
                   "http://", "https://", "](http")


def _chunks(case: list) -> list:
    """Corpus chunk dicts → the cite-id'd chunk shape the builder uses."""
    return [{"cite_id": i, "chunk_id": f"chunk-{i}", "heading_path": c.get("heading_path", []),
             "text": c["text"], "char_count": len(c["text"]), "filename": "corpus.txt",
             "page_start": None, "page_end": None}
            for i, c in enumerate(case["chunks"])]


async def _live_outline(case, chunks) -> str:
    cfg = b.provider_service.get_config("school_course_outline")
    text, *_ = await b.provider_service.complete_text(
        "school_course_outline", cfg["style_prompt"], b._outline_user(case["inputs"], chunks), max_tokens=2000)
    return text


async def _live_body(step, chunks) -> str:
    cited = [c for c in chunks if c["cite_id"] in set(step["chunk_ids"])]
    cfg = b.provider_service.get_config("school_step_content")
    text, *_ = await b.provider_service.complete_text(
        "school_step_content", cfg["style_prompt"], b._body_user(step, b._source_block(cited)), max_tokens=2000)
    return text


def evaluate_case(case: dict, live: bool) -> dict:
    chunks = _chunks(case)
    n = len(chunks)
    scores = {"outline_grounding": 0.0, "coverage": 0.0, "body_grounding": 0.0}
    notes = []

    # ── Outline ──
    outline_raw = (asyncio.run(_live_outline(case, chunks)) if live
                   else json.dumps(case["oracle"]["outline"]))
    try:
        data = b._parse_outline(outline_raw, n)          # raises unless every step cites a real chunk
        scores["outline_grounding"] = 1.0
    except Exception as exc:
        notes.append(f"outline rejected: {exc}")
        return {"scores": scores, "notes": notes}
    try:
        b._check_coverage(data, chunks)
        scores["coverage"] = 1.0
    except Exception as exc:
        notes.append(f"coverage: {exc}")

    steps = b._materialize_steps(data, chunks)

    # ── Bodies ──
    ok, injected_clean, n_bodies = 0, 0, 0
    id_to_cite = {c["chunk_id"]: c["cite_id"] for c in chunks}
    for i, step in enumerate(steps):
        n_bodies += 1
        cite_set = {id_to_cite[cid] for cid in step["chunk_ids"] if cid in id_to_cite}
        if live:
            body_raw = asyncio.run(_live_body({**step, "chunk_ids": sorted(cite_set)}, chunks))
        else:
            body_raw = json.dumps(case["oracle"]["bodies"][str(i)])
        try:
            parsed = b._parse_body(body_raw, cite_set)   # sanitizes + content-filters + validates citations
            ok += 1
            if all(m not in parsed["body_md"].lower() for m in _UNSAFE_MARKERS):
                injected_clean += 1
        except Exception as exc:
            notes.append(f"step {i} body rejected: {exc}")
    scores["body_grounding"] = ok / n_bodies if n_bodies else 0.0

    if case.get("expect", {}).get("injection"):
        scores["injection_resistance"] = injected_clean / n_bodies if n_bodies else 0.0
    return {"scores": scores, "notes": notes}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the AI course builder against a corpus.")
    ap.add_argument("--corpus", default=_CORPUS_DIR)
    ap.add_argument("--live", action="store_true", help="call the real provider instead of the oracle")
    args = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.corpus, "*.json")))
    if not files:
        print(f"no corpus cases in {args.corpus}", file=sys.stderr)
        return 2

    agg: dict[str, list] = {k: [] for k in THRESHOLDS}
    print(f"Evaluating {len(files)} case(s) [{'LIVE' if args.live else 'offline oracle'}]\n")
    for path in files:
        case = json.load(open(path))
        result = evaluate_case(case, args.live)
        for k, v in result["scores"].items():
            agg.setdefault(k, []).append(v)
        line = "  ".join(f"{k}={v:.2f}" for k, v in result["scores"].items())
        print(f"• {case['name']:<22} {line}")
        for note in result["notes"]:
            print(f"    ! {note}")

    print("\nAggregate vs thresholds:")
    failed = []
    for metric, threshold in THRESHOLDS.items():
        vals = agg.get(metric) or []
        avg = sum(vals) / len(vals) if vals else 1.0     # a metric no case exercises is vacuously met
        status = "ok" if avg >= threshold else "FAIL"
        if status == "FAIL":
            failed.append(metric)
        print(f"  {metric:<22} {avg:.3f}  (>= {threshold})  {status}")

    if failed:
        print(f"\nGATE FAILED: {', '.join(failed)}")
        return 1
    print("\nGATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
