#!/usr/bin/env python
"""Eval harness for course updates from a revised document (SC-607, gate G6).

Drives the pure update planner (`school_course_align.plan_update`) over
**revision-pair** fixtures — a published course's steps with the source text they
were built from, plus the chunks of the next edition of that document — and
scores the guarantees M6 depends on, then checks them against release thresholds
and exits non-zero if any fails. Run it on every change to the alignment
thresholds or the planner.

    python scripts/evaluate_course_update.py
    python scripts/evaluate_course_update.py --corpus path/to/dir
    python scripts/evaluate_course_update.py --mode supplement   # score one mode only

Metrics (per case, averaged):
  changed_detected      sections that really changed get a modify proposal
  unchanged_preserved   steps whose source did NOT change are never rewritten
  removed_detected      steps whose source left the document get a remove
  new_sections_detected new material no step covers gets an add proposal
  teacher_suggestion_only a change to a teacher-written step is only ever a
                       suggestion — the planner never rewrites it on its own

No model and no database: the planner decides *what* should change, which is
exactly what these thresholds are about. Body generation is scored by
`evaluate_school_course.py` (gate G4).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import school_course_align as align  # noqa: E402

_CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "school_update_eval_corpus")

# Release thresholds (gate G6): ≥90 % of changed sections detected and zero
# unchanged steps rewritten — a needless rewrite throws away a teacher's review.
THRESHOLDS = {
    "changed_detected": 0.90,
    "unchanged_preserved": 1.0,
    "removed_detected": 0.90,
    "new_sections_detected": 0.90,
    "teacher_suggestion_only": 1.0,
}


def _steps(case: dict) -> list:
    return [align.StepView(
        id=s["id"], title=s.get("title", ""), origin=s.get("origin", "ai"),
        source_text=s.get("source_text", ""),
        top_headings={h.strip().lower() for h in s.get("top_headings", []) if h},
        body_md=s.get("body_md")) for s in case["steps"]]


def _chunks(case: dict) -> list:
    return [align.ChunkView(cite_id=i, chunk_id=f"chunk-{i}",
                            heading_path=c.get("heading_path", []), text=c["text"])
            for i, c in enumerate(case["new_chunks"])]


def _norm(text) -> str:
    return " ".join((text or "").lower().split())


def _ratio(hits: int, total: int):
    """None when a case doesn't exercise the metric, so it isn't averaged in."""
    return hits / total if total else None


def evaluate_case(case: dict, mode: str = None) -> dict:
    mode = mode or case.get("mode", "revise")
    plan = align.plan_update(_steps(case), _chunks(case), mode=mode)
    expect = case["expect"]
    notes = []

    by_step: dict = {}
    auto: dict = {}
    for ch in plan["changes"]:
        if ch.step_id:
            by_step.setdefault(ch.step_id, []).append(ch.op)
            if not ch.suggestion_only:
                auto.setdefault(ch.step_id, []).append(ch.op)
    adds = [ch for ch in plan["changes"] if ch.op == "add"]

    changed = expect.get("changed", [])
    hits = [sid for sid in changed if "modify" in by_step.get(sid, [])]
    for sid in set(changed) - set(hits):
        notes.append(f"{sid}: changed source went undetected ({by_step.get(sid) or 'no proposal'})")

    unchanged = expect.get("unchanged", [])
    kept = [sid for sid in unchanged if not by_step.get(sid)]
    for sid in set(unchanged) - set(kept):
        notes.append(f"{sid}: unchanged step would be {'/'.join(by_step[sid])}")

    removed = expect.get("removed", [])
    gone = [sid for sid in removed if "remove" in by_step.get(sid, [])]
    for sid in set(removed) - set(gone):
        notes.append(f"{sid}: dropped source not detected ({by_step.get(sid) or 'no proposal'})")

    wanted = [_norm(h) for h in expect.get("new_sections", [])]
    titles = {_norm(ch.title) for ch in adds}
    found = [h for h in wanted if h in titles]
    for h in set(wanted) - set(found):
        notes.append(f"new section '{h}' not proposed (adds: {sorted(titles) or 'none'})")

    teacher = expect.get("suggestion_only", [])
    flagged = [sid for sid in teacher if by_step.get(sid) and not auto.get(sid)]
    for sid in set(teacher) - set(flagged):
        notes.append(f"{sid}: teacher step would be changed automatically ({auto.get(sid) or 'no proposal'})")

    scores = {
        "changed_detected": _ratio(len(hits), len(changed)),
        "unchanged_preserved": _ratio(len(kept), len(unchanged)),
        "removed_detected": _ratio(len(gone), len(removed)),
        "new_sections_detected": _ratio(len(found), len(wanted)),
        "teacher_suggestion_only": _ratio(len(flagged), len(teacher)),
    }
    return {"scores": scores, "notes": notes, "summary": plan["summary"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate course updates against revision-pair fixtures.")
    ap.add_argument("--corpus", default=_CORPUS_DIR)
    ap.add_argument("--mode", default=None, help="force an update mode for every case")
    args = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.corpus, "*.json")))
    if not files:
        print(f"no corpus cases in {args.corpus}", file=sys.stderr)
        return 2

    agg: dict = {k: [] for k in THRESHOLDS}
    print(f"Evaluating {len(files)} revision pair(s)\n")
    for path in files:
        case = json.load(open(path))
        result = evaluate_case(case, args.mode)
        for metric, value in result["scores"].items():
            if value is not None:
                agg[metric].append(value)
        shown = "  ".join(f"{k}={v:.2f}" for k, v in result["scores"].items() if v is not None)
        print(f"• {case['name']:<28} {shown}")
        for note in result["notes"]:
            print(f"    ! {note}")

    print("\nAggregate vs thresholds:")
    failed = []
    for metric, threshold in THRESHOLDS.items():
        vals = agg[metric]
        avg = sum(vals) / len(vals) if vals else 1.0    # a metric no case exercises is vacuously met
        ok = avg >= threshold
        failed += [] if ok else [metric]
        print(f"  {metric:<22} {avg:.3f}  (>= {threshold})  {'ok' if ok else 'FAIL'}")

    if failed:
        print(f"\nGATE FAILED: {', '.join(failed)}")
        return 1
    print("\nGATE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
