"""
Unit tests for quiz-set generation and step quiz status (phase 3).
"""
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.services.quiz_service import (
    _parse_question_list,
    generate_quiz_set,
    pass_threshold,
    step_quiz_status,
)


def _question(n):
    return {
        "intro_phrase": f"intro {n}",
        "question": f"question {n}?",
        "correct_answer": f"answer {n}",
        "answer_explanation": "because",
        "hint_1": "h1", "hint_2": "h2", "hint_3": "h3",
        "concept_tested": f"concept {n}",
    }


class TestPassThreshold:
    def test_two_of_three(self):
        assert pass_threshold(3) == 2

    def test_two_of_two(self):
        assert pass_threshold(2) == 2

    def test_scales_up(self):
        assert pass_threshold(4) == 3
        assert pass_threshold(5) == 4


class TestParseQuestionList:
    def test_parses_array(self):
        raw = json.dumps([_question(1), _question(2), _question(3)])
        assert len(_parse_question_list(raw)) == 3

    def test_parses_array_with_preamble(self):
        raw = "Here you go:\n" + json.dumps([_question(1), _question(2)]) + "\nDone."
        assert len(_parse_question_list(raw)) == 2

    def test_falls_back_to_single_object(self):
        raw = json.dumps(_question(1))
        parsed = _parse_question_list(raw)
        assert len(parsed) == 1
        assert parsed[0]["question"] == "question 1?"

    def test_drops_malformed_entries(self):
        raw = json.dumps([_question(1), {"not": "a question"}, _question(2)])
        assert len(_parse_question_list(raw)) == 2

    def test_garbage_returns_empty(self):
        assert _parse_question_list("no json here") == []


def quiz_db(fetchall_rows, insert_ids):
    """get_db mock: fetchall → recent results, fetchone → session INSERT ids."""
    ids = iter(insert_ids)

    @contextmanager
    def _get_db():
        cur = MagicMock()
        cur.fetchall.return_value = fetchall_rows
        cur.fetchone.side_effect = lambda: {"id": next(ids)}
        cur.__enter__ = lambda s: cur
        cur.__exit__ = MagicMock(return_value=False)
        conn = MagicMock()
        conn.cursor.return_value = cur
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)
        yield conn

    return _get_db


class TestGenerateQuizSet:
    @pytest.mark.asyncio
    async def test_returns_set_with_public_slice(self):
        raw = json.dumps([_question(1), _question(2), _question(3)])
        with patch("app.services.quiz_service.complete_text", return_value=(raw, 10, 20)) as ct, \
             patch("app.services.quiz_service.get_config", return_value={"style_prompt": "SP", "model": "m"}), \
             patch("app.services.quiz_service.inject_fingerprint", side_effect=lambda uid, p: p), \
             patch("app.services.quiz_service.get_db", quiz_db([], ["id1", "id2", "id3"])):
            ct.return_value = (raw, 10, 20, "m")
            result, in_tok, out_tok = await generate_quiz_set(
                "uid", "Concept", "context", journey_id="j1", step_id="s1"
            )

        assert result["pass_threshold"] == 2
        assert len(result["questions"]) == 3
        q = result["questions"][0]
        assert q["quiz_id"] == "id1"
        assert q["question"] == "question 1?"
        assert "correct_answer" not in q  # answers stay server-side
        assert (in_tok, out_tok) == (10, 20)

    @pytest.mark.asyncio
    async def test_single_object_fallback_yields_one_question_set(self):
        raw = json.dumps(_question(1))
        with patch("app.services.quiz_service.complete_text", return_value=(raw, 1, 2, "m")), \
             patch("app.services.quiz_service.get_config", return_value={"style_prompt": "SP", "model": "m"}), \
             patch("app.services.quiz_service.inject_fingerprint", side_effect=lambda uid, p: p), \
             patch("app.services.quiz_service.get_db", quiz_db([], ["id1"])):
            result, _, _ = await generate_quiz_set("uid", "Concept", "context")

        assert len(result["questions"]) == 1
        assert result["pass_threshold"] == 1

    @pytest.mark.asyncio
    async def test_no_json_raises(self):
        with patch("app.services.quiz_service.complete_text", return_value=("nope", 1, 2, "m")), \
             patch("app.services.quiz_service.get_config", return_value={"style_prompt": "SP", "model": "m"}), \
             patch("app.services.quiz_service.inject_fingerprint", side_effect=lambda uid, p: p), \
             patch("app.services.quiz_service.get_db", quiz_db([], [])):
            with pytest.raises(ValueError):
                await generate_quiz_set("uid", "Concept", "context")


def status_db(rows, skip_row=None):
    """fetchone → the skipped-check probe; fetchall → per-set aggregates."""
    @contextmanager
    def _get_db():
        cur = MagicMock()
        cur.fetchone.return_value = skip_row
        cur.fetchall.return_value = rows
        cur.__enter__ = lambda s: cur
        cur.__exit__ = MagicMock(return_value=False)
        conn = MagicMock()
        conn.cursor.return_value = cur
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)
        yield conn

    return _get_db


class TestStepQuizStatus:
    def test_no_results_not_passed(self):
        with patch("app.services.quiz_service.get_db", status_db([])):
            s = step_quiz_status("u", "j", "s")
        assert s == {"passed": False, "skipped": False, "correct": 0, "total": 0}

    def test_two_of_three_passes(self):
        rows = [{"quiz_set_id": "set1", "correct": 2, "answered": 3, "total": 3}]
        with patch("app.services.quiz_service.get_db", status_db(rows)):
            s = step_quiz_status("u", "j", "s")
        assert s["passed"] is True

    def test_one_of_three_fails(self):
        rows = [{"quiz_set_id": "set1", "correct": 1, "answered": 3, "total": 3}]
        with patch("app.services.quiz_service.get_db", status_db(rows)):
            s = step_quiz_status("u", "j", "s")
        assert s["passed"] is False
        assert s["correct"] == 1

    def test_unanswered_questions_block_pass(self):
        rows = [{"quiz_set_id": "set1", "correct": 2, "answered": 2, "total": 3}]
        with patch("app.services.quiz_service.get_db", status_db(rows)):
            s = step_quiz_status("u", "j", "s")
        assert s["passed"] is False

    def test_any_passing_set_wins_over_failed_retries(self):
        rows = [
            {"quiz_set_id": "set1", "correct": 0, "answered": 3, "total": 3},
            {"quiz_set_id": "set2", "correct": 3, "answered": 3, "total": 3},
        ]
        with patch("app.services.quiz_service.get_db", status_db(rows)):
            s = step_quiz_status("u", "j", "s")
        assert s["passed"] is True
        assert s["correct"] == 3

    def test_explicit_skip_opens_the_gate(self):
        with patch("app.services.quiz_service.get_db", status_db([], skip_row={"?column?": 1})):
            s = step_quiz_status("u", "j", "s")
        assert s["passed"] is True
        assert s["skipped"] is True

    def test_unskipped_results_report_skipped_false(self):
        rows = [{"quiz_set_id": "set1", "correct": 2, "answered": 3, "total": 3}]
        with patch("app.services.quiz_service.get_db", status_db(rows)):
            s = step_quiz_status("u", "j", "s")
        assert s["passed"] is True
        assert s["skipped"] is False
