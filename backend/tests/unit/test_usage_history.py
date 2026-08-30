"""
Phase 7 — Admin observability and usage history.

Verifies:
- get_usage_history returns rows newest-first and caps at 24 months.
- get_usage_breakdown returns rows ordered by cost descending.
- No 'unknown' interaction_type appears (all endpoints pass the kwarg).
- Admin stats API endpoint returns correctly shaped response.
"""
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import (
    TEST_UID, FREE_TRIAL, INDIVIDUAL, mock_db, mock_db_fetchall, usage, extras,
)


# ═══════════════════════════════════════════════════════════════════════════════
# get_usage_history
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUsageHistory:

    def test_returns_rows_newest_first(self):
        from app.services.subscription_service import get_usage_history
        from datetime import date

        rows = [
            {"period_start": date(2026, 6, 1), "estimated_cost_cents": 50.0, "message_count": 10,
             "input_tokens": 1000, "output_tokens": 500, "cached_input_tokens": 0},
            {"period_start": date(2026, 5, 1), "estimated_cost_cents": 30.0, "message_count": 6,
             "input_tokens": 600, "output_tokens": 300, "cached_input_tokens": 0},
            {"period_start": date(2026, 4, 1), "estimated_cost_cents": 10.0, "message_count": 2,
             "input_tokens": 200, "output_tokens": 100, "cached_input_tokens": 0},
        ]
        with patch("app.services.subscription_service.get_db", mock_db_fetchall(rows)):
            history = get_usage_history(TEST_UID, months=6)

        assert len(history) == 3
        periods = [r["period_start"] for r in history]
        assert periods == sorted(periods, reverse=True), "Must be returned newest first"

    def test_empty_history_returns_empty_list(self):
        from app.services.subscription_service import get_usage_history

        with patch("app.services.subscription_service.get_db", mock_db_fetchall([])):
            result = get_usage_history(TEST_UID)

        assert result == []

    def test_months_capped_at_24(self):
        """SQL must not request more than 24 months — prevents table scan."""
        from app.services.subscription_service import get_usage_history

        executed_params = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed_params.append(params)
            cur.fetchall.return_value = []
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            get_usage_history(TEST_UID, months=999)

        assert executed_params and executed_params[0][1] == 24, \
            "months must be capped at 24 in the SQL params"

    def test_default_months_is_6(self):
        from app.services.subscription_service import get_usage_history

        executed_params = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed_params.append(params)
            cur.fetchall.return_value = []
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            get_usage_history(TEST_UID)  # no months arg

        assert executed_params and executed_params[0][1] == 6


# ═══════════════════════════════════════════════════════════════════════════════
# get_usage_breakdown
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetUsageBreakdown:

    def test_breakdown_ordered_by_cost_descending(self):
        from app.services.subscription_service import get_usage_breakdown

        rows = [
            {"interaction_type": "daily_chat",   "estimated_cost_cents": 30.0,
             "request_count": 50, "input_tokens": 5000, "output_tokens": 2000, "cached_input_tokens": 0},
            {"interaction_type": "step_content", "estimated_cost_cents": 15.0,
             "request_count": 10, "input_tokens": 2000, "output_tokens": 1000, "cached_input_tokens": 0},
            {"interaction_type": "spark",        "estimated_cost_cents": 5.0,
             "request_count": 100, "input_tokens": 3000, "output_tokens": 1000, "cached_input_tokens": 0},
        ]
        with patch("app.services.subscription_service.get_db", mock_db_fetchall(rows)):
            breakdown = get_usage_breakdown(TEST_UID)

        costs = [r["estimated_cost_cents"] for r in breakdown]
        assert costs == sorted(costs, reverse=True), "Breakdown must be ordered by cost DESC"

    def test_empty_breakdown_returns_empty_list(self):
        from app.services.subscription_service import get_usage_breakdown

        with patch("app.services.subscription_service.get_db", mock_db_fetchall([])):
            result = get_usage_breakdown(TEST_UID)

        assert result == []

    def test_breakdown_includes_all_fields(self):
        from app.services.subscription_service import get_usage_breakdown

        row = {
            "interaction_type": "quiz", "estimated_cost_cents": 2.0,
            "request_count": 5, "input_tokens": 500,
            "output_tokens": 200, "cached_input_tokens": 0,
        }
        with patch("app.services.subscription_service.get_db", mock_db_fetchall([row])):
            result = get_usage_breakdown(TEST_UID)

        assert len(result) == 1
        r = result[0]
        assert "interaction_type"      in r
        assert "estimated_cost_cents"  in r
        assert "request_count"         in r
        assert "input_tokens"          in r
        assert "output_tokens"         in r


# ═══════════════════════════════════════════════════════════════════════════════
# No 'unknown' interaction type
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoUnknownInteractionType:

    KNOWN_INTERACTION_TYPES = {
        "daily_chat", "onboarding", "fingerprint", "mind_signature",
        "spark", "daily_spark", "knowledge_extraction",
        "journey", "step_content", "content_critic", "quiz", "nudge",
        "journey_tutor", "journey_image", "visual_planner", "visual_recipe", "visual_image",
    }

    def test_all_provider_default_config_types_are_known(self):
        """Every interaction type in DEFAULT_CONFIG must be in our KNOWN set."""
        from app.services.provider_service import DEFAULT_CONFIG
        configured = set(DEFAULT_CONFIG.keys())
        unknown = configured - self.KNOWN_INTERACTION_TYPES
        assert not unknown, \
            f"New interaction types not added to KNOWN_INTERACTION_TYPES: {unknown}"

    def test_no_endpoint_calls_record_usage_without_interaction_type(self):
        """Static AST check — duplicated here for discoverability."""
        import ast
        import pathlib

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
            "record_usage missing interaction_type:\n" + "\n".join(violations)


# ═══════════════════════════════════════════════════════════════════════════════
# Admin stats API
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdminStats:

    @pytest.fixture
    def client(self):
        from app.main import app
        from app.core.auth import get_required_user, get_admin_user
        from fastapi.testclient import TestClient

        saved = dict(app.dependency_overrides)
        app.dependency_overrides[get_required_user] = lambda: TEST_UID
        app.dependency_overrides[get_admin_user]    = lambda: TEST_UID

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)

    def test_admin_stats_returns_200(self, client):
        with patch("app.api.v1.endpoints.admin.get_admin_stats", return_value={
            "total_users": 50,
            "dau": 10,
            "messages_today": 80,
            "monthly_api_cost_cents": 3500.0,
        }):
            res = client.get("/api/v1/admin/stats")
        assert res.status_code == 200

    def test_admin_stats_contains_monthly_cost(self, client):
        with patch("app.api.v1.endpoints.admin.get_admin_stats", return_value={
            "total_users": 50,
            "dau": 10,
            "messages_today": 80,
            "monthly_api_cost_cents": 3500.0,
        }):
            res = client.get("/api/v1/admin/stats")
        body = res.json()
        assert "monthly_api_cost_cents" in body
        assert body["monthly_api_cost_cents"] >= 0

    def test_admin_stats_monthly_cost_sums_all_users(self):
        """get_admin_stats SQL sums token_usage.estimated_cost_cents across all users."""
        from app.services.subscription_service import get_admin_stats

        row = {
            "total_users": 100,
            "dau": 25,
            "messages_today": 200,
            "monthly_cost_cents": 5000.0,
        }
        with patch("app.services.subscription_service.get_db", mock_db(row)):
            stats = get_admin_stats()

        assert stats["monthly_api_cost_cents"] == 5000.0
        assert stats["total_users"] == 100
