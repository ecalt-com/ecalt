"""Pure-logic unit tests for school analytics (no DB): struggling flags
(SC-702, UNIT-FLAG) and CSV formula-injection escaping (SC-704, SEC-12)."""
from app.services.school_analytics_service import csv_escape, struggle_flags


# ── struggle_flags ───────────────────────────────────────────────────────────

def test_no_flags_for_a_clean_record():
    assert struggle_flags({"overdue": False, "attempts": 10, "accuracy": 0.9,
                           "hints": 0, "quizzed_steps": 3, "stalled": False}) == []


def test_overdue_flag():
    assert "overdue" in struggle_flags({"overdue": True})


def test_low_accuracy_only_with_enough_attempts():
    assert "low_quiz_accuracy" in struggle_flags({"attempts": 4, "accuracy": 0.25})
    # Too few attempts to judge.
    assert "low_quiz_accuracy" not in struggle_flags({"attempts": 2, "accuracy": 0.0})
    # No attempts → accuracy is None → never flagged.
    assert struggle_flags({"attempts": 0, "accuracy": None}) == []


def test_heavy_hints_flag():
    assert "heavy_hints" in struggle_flags({"quizzed_steps": 2, "hints": 5})
    assert "heavy_hints" not in struggle_flags({"quizzed_steps": 2, "hints": 1})


def test_stalled_flag():
    assert struggle_flags({"stalled": True}) == ["stalled"]


# ── csv_escape (SEC-12) ──────────────────────────────────────────────────────

def test_plain_values_unchanged():
    assert csv_escape("Asha") == "Asha"
    assert csv_escape("3/5") == "3/5"
    assert csv_escape(None) == ""
    assert csv_escape(7) == "7"


def test_formula_leads_are_neutralised():
    # A leading apostrophe is prepended to every dangerous lead. (A CR cell is
    # then also CSV-quoted, so check the apostrophe is present, not leading.)
    for lead in ("=", "+", "-", "@", "\t", "\r"):
        assert ("'" + lead) in csv_escape(f"{lead}cmd")
    assert csv_escape("=SUM(A1:A9)") == "'=SUM(A1:A9)"


def test_separators_and_quotes_force_quoting():
    assert csv_escape("a,b") == '"a,b"'
    assert csv_escape('say "hi"') == '"say ""hi"""'
    assert csv_escape("line1\nline2") == '"line1\nline2"'


def test_formula_lead_and_comma_together():
    # Neutralised first, then quoted because of the comma.
    assert csv_escape("=a,b") == '"\'=a,b"'
