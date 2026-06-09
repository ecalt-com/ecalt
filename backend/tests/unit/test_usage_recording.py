"""
Phase 3 — Usage recording correctness.

Verifies:
- Every AI endpoint records REAL token counts (never zero).
- Both token_usage and usage_by_interaction tables receive writes.
- The correct interaction_type is passed to every record_usage call.
- No endpoint calls record_usage(uid, 0, 0, ...).
"""
import ast
import pathlib
from contextlib import contextmanager
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from tests.conftest import TEST_UID, mock_db, mock_db_fetchall


# ═══════════════════════════════════════════════════════════════════════════════
# Static analysis — no zero-token calls in any endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoZeroTokenCalls:

    def test_no_record_usage_with_literal_zero_tokens(self):
        """
        Static check: no endpoint module may call record_usage(uid, 0, 0, ...).
        Quiz used to do this (G1) — verify it's fixed everywhere.
        """
        endpoints_dir = pathlib.Path("app/api/v1/endpoints")
        violations = []

        for pyfile in endpoints_dir.glob("*.py"):
            src = pyfile.read_text(encoding="utf-8")
            if "record_usage" not in src:
                continue
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                # Match both record_usage(...) and module.record_usage(...)
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name != "record_usage":
                    continue
                # args: uid, in_tok, out_tok, model — check positions 1 and 2 (0-indexed)
                if len(node.args) >= 3:
                    in_arg  = node.args[1]
                    out_arg = node.args[2]
                    if (isinstance(in_arg, ast.Constant) and in_arg.value == 0 and
                            isinstance(out_arg, ast.Constant) and out_arg.value == 0):
                        violations.append(f"{pyfile.name}:L{node.lineno}")

        assert not violations, \
            f"record_usage(uid, 0, 0, ...) found — tokens must come from the AI response:\n" + \
            "\n".join(violations)

    def test_all_record_usage_calls_have_interaction_type(self):
        """Every record_usage call site in endpoints must pass interaction_type."""
        endpoints_dir = pathlib.Path("app/api/v1/endpoints")
        violations = []

        for pyfile in endpoints_dir.glob("*.py"):
            src = pyfile.read_text(encoding="utf-8")
            if "record_usage" not in src:
                continue
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name != "record_usage":
                    continue
                kwargs = {kw.arg for kw in node.keywords}
                if "interaction_type" not in kwargs:
                    violations.append(f"{pyfile.name}:L{node.lineno}")

        assert not violations, \
            "record_usage missing interaction_type kwarg:\n" + "\n".join(violations)


# ═══════════════════════════════════════════════════════════════════════════════
# Quiz — real tokens flow through
# ═══════════════════════════════════════════════════════════════════════════════

class TestQuizRecordsRealTokens:

    @pytest.fixture
    def client(self):
        from app.main import app
        from app.core.auth import get_required_user
        from fastapi.testclient import TestClient

        saved = dict(app.dependency_overrides)
        app.dependency_overrides[get_required_user] = lambda: TEST_UID

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)

    def test_quiz_records_nonzero_tokens(self, client):
        recorded = []

        def spy(uid, in_tok, out_tok, model, interaction_type="unknown", **kw):
            recorded.append({"in": in_tok, "out": out_tok})

        sample_quiz = {
            "quiz_id":      "qid-001",
            "concept":      "gravity",
            "difficulty":   "exploratory",
            "intro_phrase": "Before we go further —",
            "question":     "What does a heavier object tell us about spacetime?",
            "hint_available": 3,
        }

        with patch("app.api.v1.endpoints.quiz.check_budget",    return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.quiz.generate_quiz",
                   new_callable=AsyncMock, return_value=(sample_quiz, 350, 180)), \
             patch("app.api.v1.endpoints.quiz.record_usage",    side_effect=spy):
            res = client.post("/api/v1/quiz",
                              json={"concept": "gravity", "context": "We discussed Newton"})

        assert res.status_code == 200
        assert len(recorded) == 1
        assert recorded[0]["in"] == 350,  "Input tokens must be real value from AI"
        assert recorded[0]["out"] == 180, "Output tokens must be real value from AI"

    def test_quiz_never_records_zero_tokens_on_success(self, client):
        """Even with a minimal AI response, tokens must be > 0."""
        sample_quiz = {"quiz_id": "q1", "concept": "x", "difficulty": "surface",
                       "intro_phrase": "", "question": "Q?", "hint_available": 3}

        recorded = []
        with patch("app.api.v1.endpoints.quiz.check_budget",   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.quiz.generate_quiz",
                   new_callable=AsyncMock, return_value=(sample_quiz, 100, 50)), \
             patch("app.api.v1.endpoints.quiz.record_usage",
                   side_effect=lambda uid, in_tok, out_tok, model, **kw: recorded.append((in_tok, out_tok))):
            client.post("/api/v1/quiz", json={"concept": "x", "context": "ctx"})

        assert recorded and recorded[0][0] > 0 and recorded[0][1] > 0

    def test_quiz_interaction_type_is_quiz(self, client):
        types = []
        sample = {"quiz_id": "q1", "concept": "x", "difficulty": "surface",
                  "intro_phrase": "", "question": "Q?", "hint_available": 3}

        with patch("app.api.v1.endpoints.quiz.check_budget",   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.quiz.generate_quiz",
                   new_callable=AsyncMock, return_value=(sample, 100, 50)), \
             patch("app.api.v1.endpoints.quiz.record_usage",
                   side_effect=lambda uid, in_tok, out_tok, model,
                   interaction_type="unknown", **kw: types.append(interaction_type)):
            client.post("/api/v1/quiz", json={"concept": "x", "context": "ctx"})

        assert types == ["quiz"]


# ═══════════════════════════════════════════════════════════════════════════════
# record_usage writes BOTH tables
# ═══════════════════════════════════════════════════════════════════════════════

class TestBothTablesWritten:

    def _capture_sqls(self):
        executed = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed.append(sql)
            cur.fetchone.return_value = {"estimated_cost_cents": 0.02, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        return capture_db, executed

    def test_token_usage_table_written(self):
        from app.services.subscription_service import record_usage
        capture_db, sqls = self._capture_sqls()

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 500, 200, "gpt-4o-mini", interaction_type="daily_chat")

        assert any("token_usage" in s for s in sqls), "token_usage INSERT missing"

    def test_usage_by_interaction_table_written(self):
        from app.services.subscription_service import record_usage
        capture_db, sqls = self._capture_sqls()

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 500, 200, "gpt-4o-mini", interaction_type="daily_chat")

        assert any("usage_by_interaction" in s for s in sqls), \
            "usage_by_interaction INSERT missing"

    def test_both_tables_use_upsert(self):
        from app.services.subscription_service import record_usage
        capture_db, sqls = self._capture_sqls()

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 50, "gpt-4.1-nano", interaction_type="spark")

        upserts = [s for s in sqls if "ON CONFLICT" in s]
        assert len(upserts) >= 2, "Both tables must use ON CONFLICT upsert"

    def test_interaction_type_stored_in_usage_by_interaction(self):
        from app.services.subscription_service import record_usage

        captured_interaction_params = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            def execute_side(sql, params=None):
                if params and "usage_by_interaction" in sql:
                    captured_interaction_params.append(params)
            cur.execute.side_effect = execute_side
            cur.fetchone.return_value = {"estimated_cost_cents": 0.01, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 50, "gpt-4o-mini", interaction_type="step_content")

        assert captured_interaction_params, "usage_by_interaction INSERT never executed"
        # params: (uid, period_start, interaction_type, input_tokens, ...)
        assert captured_interaction_params[0][2] == "step_content"

    @pytest.mark.parametrize("interaction_type", [
        "daily_chat", "step_content", "journey", "spark", "daily_spark",
        "quiz", "mind_signature", "knowledge_extraction", "fingerprint",
    ])
    def test_all_known_interaction_types_stored_correctly(self, interaction_type):
        from app.services.subscription_service import record_usage

        stored = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            def execute_side(sql, params=None):
                if params and "usage_by_interaction" in sql:
                    stored.append(params[2])
            cur.execute.side_effect = execute_side
            cur.fetchone.return_value = {"estimated_cost_cents": 0.01, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 50, "gpt-4o-mini", interaction_type=interaction_type)

        assert stored == [interaction_type]
