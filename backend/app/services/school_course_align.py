"""Align a published course's steps to a new document's chunks and plan a change
set (M6 SC-601/602).

Pure and dependency-free so it unit-tests without a DB or a model. Given a
course's published steps (each carrying the text of the source chunks it was
built from) and the chunks of a NEW document, it classifies every step as
``unchanged`` / ``source_changed`` / ``source_removed`` by lexical overlap
(token Jaccard with a heading-path boost — no embeddings in v1) and collects the
new sections no step covers. :func:`plan_update` turns that into an ordered list
of proposed changes (``modify`` / ``add`` / ``remove``), honouring the update
mode and never auto-modifying or auto-removing a teacher-authored step (for
those a change is a *suggestion only*).

The planner does **not** generate step bodies — that needs the model and happens
in the job (`school_course_update_service`). It only decides what should change
and which NEW chunks each change should be grounded in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# A step is "the same section, unchanged" above this, "the same section but
# edited" down to CHANGED, and "no longer in the document" below CHANGED.
UNCHANGED_THRESHOLD = 0.82
CHANGED_THRESHOLD = 0.22
# A new chunk counts as "covered" by a step (so it isn't proposed as a new
# section) once a step matches it at least this well.
COVER_THRESHOLD = 0.22
# Added to a chunk's score when it shares the step's top-level heading.
_HEADING_BOOST = 0.10

_WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> set:
    """Lowercase word tokens (length ≥ 2) as a set, for Jaccard overlap."""
    return {w for w in _WORD_RE.findall((text or "").lower()) if len(w) >= 2}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def _top_heading(path) -> str:
    return ((path[0] if path else "") or "").strip().lower()


@dataclass
class StepView:
    """What the planner needs about one published step."""
    id: str
    title: str
    origin: str = "ai"
    source_text: str = ""          # concatenated text of the chunks it was built from
    top_headings: set = field(default_factory=set)
    body_md: Optional[str] = None


@dataclass
class ChunkView:
    """What the planner needs about one chunk of the NEW document."""
    cite_id: int
    chunk_id: str
    heading_path: list = field(default_factory=list)
    text: str = ""


def _score(step_tokens: set, step_headings: set, chunk: ChunkView, chunk_tokens: set) -> float:
    s = jaccard(step_tokens, chunk_tokens)
    if step_headings and _top_heading(chunk.heading_path) in step_headings:
        s = min(1.0, s + _HEADING_BOOST)
    return s


def _rank(step_tokens: set, step_headings: set, new_chunks: list, chunk_tokens: dict) -> list:
    """New chunks scored against a step, best first: ``[(chunk, score), …]``."""
    scored = [(c, _score(step_tokens, step_headings, c, chunk_tokens[c.cite_id])) for c in new_chunks]
    scored.sort(key=lambda cs: cs[1], reverse=True)
    return scored


def classify(best_score: float) -> str:
    if best_score >= UNCHANGED_THRESHOLD:
        return "unchanged"
    if best_score >= CHANGED_THRESHOLD:
        return "source_changed"
    return "source_removed"


@dataclass
class Change:
    op: str                        # 'modify' | 'add' | 'remove'
    step_id: Optional[str] = None  # the existing step for modify/remove
    after_step_id: Optional[str] = None   # placement for add
    matched_chunk_ids: list = field(default_factory=list)  # NEW chunk ids to ground on
    reason: str = ""
    suggestion_only: bool = False  # teacher-authored steps are never changed automatically
    title: str = ""                # suggested title for an add


def _group_uncovered(new_chunks: list, covered: set) -> list:
    """Uncovered new chunks grouped into consecutive runs sharing a top heading.
    Returns ``[[ChunkView, …], …]`` in document order."""
    groups: list = []
    current: list = []
    current_head = None
    for c in new_chunks:
        if c.chunk_id in covered:
            if current:
                groups.append(current)
                current, current_head = [], None
            continue
        head = _top_heading(c.heading_path)
        if current and head != current_head:
            groups.append(current)
            current = []
        current.append(c)
        current_head = head
    if current:
        groups.append(current)
    return groups


def _add_title(group: list) -> str:
    head = (group[0].heading_path[0] if group[0].heading_path else "").strip()
    return (head or "New material")[:200]


def plan_update(steps: list, new_chunks: list, mode: str = "revise") -> dict:
    """Plan a change set for updating ``steps`` from ``new_chunks``.

    ``steps`` are :class:`StepView`, ``new_chunks`` are :class:`ChunkView` in
    document order. ``mode`` is ``'revise'`` (reclassify every step + add new
    sections) or ``'supplement'`` (only add new sections; never touch existing
    steps). Returns ``{"changes": [Change…], "classifications": {id: str},
    "covered_chunk_ids": set, "summary": {…}}``.
    """
    chunk_tokens = {c.cite_id: tokenize(c.text) for c in new_chunks}
    classifications: dict = {}
    changes: list = []
    covered: set = set()

    for step in steps:
        st_tokens = tokenize(step.source_text)
        ranked = _rank(st_tokens, step.top_headings, new_chunks, chunk_tokens)
        best_score = ranked[0][1] if ranked else 0.0
        kind = classify(best_score)
        classifications[step.id] = kind

        # Chunks this step still "owns" (so they aren't re-proposed as new).
        matched = [c for c, sc in ranked if sc >= COVER_THRESHOLD]
        for c in matched:
            covered.add(c.chunk_id)

        if mode == "supplement":
            continue   # supplement never modifies or removes existing steps
        if kind == "unchanged":
            continue

        is_teacher = step.origin == "teacher"
        if kind == "source_changed":
            changes.append(Change(
                op="modify", step_id=step.id,
                matched_chunk_ids=[c.chunk_id for c in matched[:4]] or [ranked[0][0].chunk_id],
                reason="The source material for this step changed in the new document.",
                suggestion_only=is_teacher))
        else:  # source_removed
            changes.append(Change(
                op="remove", step_id=step.id,
                reason="This step's source material is no longer in the new document.",
                suggestion_only=is_teacher))

    # New sections no step covers → propose add steps (both modes).
    for group in _group_uncovered(new_chunks, covered):
        group_tokens: set = set()
        for c in group:
            group_tokens |= chunk_tokens[c.cite_id]
        after = _best_preceding_step(steps, group_tokens)
        changes.append(Change(
            op="add", after_step_id=after,
            matched_chunk_ids=[c.chunk_id for c in group],
            reason="A new section in the document that no existing step covers.",
            title=_add_title(group)))

    summary = {
        "unchanged": sum(1 for k in classifications.values() if k == "unchanged"),
        "modify": sum(1 for c in changes if c.op == "modify"),
        "add": sum(1 for c in changes if c.op == "add"),
        "remove": sum(1 for c in changes if c.op == "remove"),
    }
    return {"changes": changes, "classifications": classifications,
            "covered_chunk_ids": covered, "summary": summary}


def _best_preceding_step(steps: list, group_tokens: set) -> Optional[str]:
    """Place an added section after the existing step whose source overlaps it
    most, so new material lands near related content; None → append at the end."""
    best_id, best = None, 0.0
    for step in steps:
        sc = jaccard(tokenize(step.source_text), group_tokens)
        if sc > best:
            best, best_id = sc, step.id
    return best_id
