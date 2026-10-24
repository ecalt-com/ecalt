"""SC-411: the AI-course-builder eval harness passes its own corpus offline.

Keeps the harness (scripts/evaluate_school_course.py) runnable and the grounding
+ injection-resistance thresholds green in CI. `--live` runs are manual ($$).
"""
import glob
import importlib.util
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HARNESS = os.path.join(_ROOT, "scripts", "evaluate_school_course.py")


def _load():
    spec = importlib.util.spec_from_file_location("evaluate_school_course", _HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_corpus_case_meets_thresholds():
    h = _load()
    files = sorted(glob.glob(os.path.join(h._CORPUS_DIR, "*.json")))
    assert files, "no eval corpus cases found"
    for path in files:
        case = json.load(open(path))
        scores = h.evaluate_case(case, live=False)["scores"]
        for metric, value in scores.items():
            assert value >= h.THRESHOLDS[metric], f"{case['name']}: {metric}={value}"


def test_harness_gate_passes_offline():
    h = _load()
    assert h.main([]) == 0


def test_injection_case_actually_contains_an_attack():
    # guards against the corpus being watered down to pass trivially
    h = _load()
    inj = json.load(open(os.path.join(h._CORPUS_DIR, "injection_defense.json")))
    raw = inj["oracle"]["bodies"]["0"]["body_md"].lower()
    assert "<script" in raw and "http://evil" in raw
