"""Pure-logic unit tests for course-update alignment (no DB, no model):
classification + the change plan for revise/supplement modes (M6 SC-601/602)."""
from app.services import school_course_align as align
from app.services.school_course_align import ChunkView, StepView, jaccard, plan_update


# ── similarity + classification ──────────────────────────────────────────────

def test_jaccard_basic():
    assert jaccard(set(), {"a"}) == 0.0
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_classify_bands():
    assert align.classify(0.95) == "unchanged"
    assert align.classify(0.5) == "source_changed"
    assert align.classify(0.05) == "source_removed"


# Shared vocabulary so Jaccard behaves predictably.
_WATER = "the water cycle describes how water evaporates condenses and falls as precipitation"
_WATER_EDITED = "the water cycle describes how water evaporates condenses and returns as rain and snow runoff"
_PHOTO = "photosynthesis lets plants convert sunlight carbon dioxide and water into glucose and oxygen"


def _step(sid, text, origin="ai", headings=None):
    return StepView(id=sid, title=sid, origin=origin, source_text=text,
                    top_headings=set(headings or []))


def _chunk(i, text, heading=None):
    return ChunkView(cite_id=i, chunk_id=f"c{i}", heading_path=[heading] if heading else [], text=text)


# ── revise mode ──────────────────────────────────────────────────────────────

def test_unchanged_step_yields_no_change():
    steps = [_step("s1", _WATER)]
    new = [_chunk(0, _WATER)]
    plan = plan_update(steps, new, mode="revise")
    assert plan["classifications"]["s1"] == "unchanged"
    assert plan["changes"] == []


def test_edited_source_proposes_modify():
    steps = [_step("s1", _WATER)]
    new = [_chunk(0, _WATER_EDITED)]
    plan = plan_update(steps, new, mode="revise")
    assert plan["classifications"]["s1"] == "source_changed"
    ops = [(c.op, c.step_id) for c in plan["changes"]]
    assert ("modify", "s1") in ops
    mod = next(c for c in plan["changes"] if c.op == "modify")
    assert mod.matched_chunk_ids == ["c0"] and not mod.suggestion_only


def test_removed_source_proposes_remove():
    steps = [_step("s1", _WATER)]
    new = [_chunk(0, _PHOTO)]   # the new doc is about something else entirely
    plan = plan_update(steps, new, mode="revise")
    assert plan["classifications"]["s1"] == "source_removed"
    assert any(c.op == "remove" and c.step_id == "s1" for c in plan["changes"])


def test_teacher_step_change_is_suggestion_only():
    steps = [_step("s1", _WATER, origin="teacher")]
    new = [_chunk(0, _WATER_EDITED)]
    plan = plan_update(steps, new, mode="revise")
    mod = next(c for c in plan["changes"] if c.step_id == "s1")
    assert mod.suggestion_only is True


def test_new_section_proposes_add():
    steps = [_step("s1", _WATER)]
    new = [_chunk(0, _WATER), _chunk(1, _PHOTO, heading="Photosynthesis")]
    plan = plan_update(steps, new, mode="revise")
    adds = [c for c in plan["changes"] if c.op == "add"]
    assert len(adds) == 1
    assert adds[0].matched_chunk_ids == ["c1"]
    assert adds[0].title == "Photosynthesis"
    # the unchanged water step produces no modify/remove
    assert not any(c.op in ("modify", "remove") for c in plan["changes"])


# ── supplement mode ──────────────────────────────────────────────────────────

def test_supplement_only_adds_never_modifies():
    steps = [_step("s1", _WATER)]
    new = [_chunk(0, _WATER_EDITED), _chunk(1, _PHOTO, heading="Photosynthesis")]
    plan = plan_update(steps, new, mode="supplement")
    assert all(c.op == "add" for c in plan["changes"])
    # the edited water chunk is "covered" by s1, so only the new photo section is added
    assert [c.matched_chunk_ids for c in plan["changes"]] == [["c1"]]


def test_add_placed_after_most_related_step():
    steps = [_step("s1", _WATER), _step("s2", _PHOTO)]
    # A new section overlapping the photosynthesis step most is placed after it;
    # unrelated material appends at the end (None).
    photo_ish = align.tokenize("glucose oxygen photosynthesis chlorophyll plants")
    assert align._best_preceding_step(steps, photo_ish) == "s2"
    assert align._best_preceding_step(steps, align.tokenize("quantum entanglement qubits")) is None
