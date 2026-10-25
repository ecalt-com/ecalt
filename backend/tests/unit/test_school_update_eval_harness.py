"""SC-607: the course-update eval harness passes its own revision-pair corpus.

Keeps `scripts/evaluate_course_update.py` runnable and gate G6 (≥90 % of changed
sections detected, zero unchanged steps rewritten) green in CI. The harness is
pure — no model and no database — so it runs with the ordinary unit suite.
"""
import glob
import importlib.util
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_HARNESS = os.path.join(_ROOT, "scripts", "evaluate_course_update.py")


def _load():
    spec = importlib.util.spec_from_file_location("evaluate_course_update", _HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cases(h):
    return sorted(glob.glob(os.path.join(h._CORPUS_DIR, "*.json")))


def test_every_revision_pair_meets_thresholds():
    h = _load()
    files = _cases(h)
    assert files, "no update eval corpus cases found"
    for path in files:
        case = json.load(open(path))
        for metric, value in h.evaluate_case(case)["scores"].items():
            if value is not None:
                assert value >= h.THRESHOLDS[metric], f"{case['name']}: {metric}={value}"


def test_harness_gate_passes():
    assert _load().main([]) == 0


def test_corpus_actually_exercises_every_metric():
    # guards against the corpus being watered down until the gate is vacuous
    h = _load()
    exercised = {m for path in _cases(h)
                 for m, v in h.evaluate_case(json.load(open(path)))["scores"].items() if v is not None}
    assert exercised == set(h.THRESHOLDS), f"never scored: {set(h.THRESHOLDS) - exercised}"


def test_a_missed_rewrite_fails_the_gate():
    # a case that expects an unchanged step must fail if the planner would touch it
    h = _load()
    case = json.load(open(os.path.join(h._CORPUS_DIR, "water_cycle_2e.json")))
    case["expect"]["unchanged"] = ["s2"]          # s2's source really did change
    scores = h.evaluate_case(case)["scores"]
    assert scores["unchanged_preserved"] < h.THRESHOLDS["unchanged_preserved"]
