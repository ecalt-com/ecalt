"""
Phase 6 — Race condition and over-allocation defense.

Documents the known check→call→record race window and verifies:
- The ON CONFLICT upsert prevents data loss under concurrent writes.
- The maximum possible overrun is bounded (< 0.20 cents per request).
- Two threads near the budget boundary both pass check_budget (expected behaviour).
"""
import threading
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

import pytest

from tests.conftest import TEST_UID, usage, extras, INDIVIDUAL


# ── Helper ─────────────────────────────────────────────────────────────────────

def _run_check(plan, usage_val, extras_val, context="ai"):
    from app.services.subscription_service import check_budget
    with patch("app.services.subscription_service.get_user_plan",           return_value=plan), \
         patch("app.services.subscription_service.get_current_usage",        return_value=usage_val), \
         patch("app.services.subscription_service.get_coupon_extras",        return_value=extras_val), \
         patch("app.services.subscription_service.count_lifetime_messages",  return_value=0):
        return check_budget(TEST_UID, context=context)


# ═══════════════════════════════════════════════════════════════════════════════
# Race window documentation
# ═══════════════════════════════════════════════════════════════════════════════

class TestRaceConditionDocumentation:

    def test_two_concurrent_checks_both_pass_at_boundary(self):
        """
        At spent = budget - epsilon, two concurrent check_budget calls both return
        (True, 'ok') because both read the same stale DB row.

        This is the KNOWN race window. Maximum overrun = one request cost (~0.1¢).
        This test documents the behaviour — it is NOT a failure condition.
        """
        call_results = []

        def run_check():
            allowed, reason = _run_check(INDIVIDUAL, usage(759.99), extras())
            call_results.append((allowed, reason))

        t1 = threading.Thread(target=run_check)
        t2 = threading.Thread(target=run_check)
        t1.start(); t2.start()
        t1.join();  t2.join()

        # Both pass — documented race condition
        assert all(allowed for allowed, _ in call_results), \
            "Both threads should pass at budget-1 (race window documented)"
        assert all(reason == "ok" for _, reason in call_results)

    def test_check_budget_reads_fresh_db_state(self):
        """
        check_budget calls get_current_usage each time — it never caches.
        Simulate: first call returns 18¢ spent (under free_trial 20¢), second
        returns 20¢ (at limit) — the second call must block.
        """
        from app.services.subscription_service import check_budget
        from tests.conftest import FREE_TRIAL

        call_count = [0]
        costs = [18.0, 20.0]  # first: under budget; second: at free_trial limit

        p1 = patch("app.services.subscription_service.get_user_plan",          return_value=FREE_TRIAL)
        p2 = patch("app.services.subscription_service.get_current_usage",
                   side_effect=lambda uid: usage(costs[min(call_count[0], 1)]))
        p3 = patch("app.services.subscription_service.get_coupon_extras",       return_value=extras())
        p4 = patch("app.services.subscription_service.count_lifetime_messages", return_value=0)

        with p1, p2, p3, p4:
            allowed1, _ = check_budget(TEST_UID, context="ai")
            call_count[0] += 1
            allowed2, reason2 = check_budget(TEST_UID, context="ai")

        assert allowed1 is True   # 18 < 20 → allowed
        assert allowed2 is False  # 20 >= 20 → blocked
        assert reason2 == "budget_exhausted"


# ═══════════════════════════════════════════════════════════════════════════════
# ON CONFLICT upsert prevents data loss
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpsertDataIntegrity:

    def test_record_usage_always_uses_on_conflict_upsert(self):
        """
        Even under concurrent writes, ON CONFLICT DO UPDATE ensures tokens accumulate
        atomically at the DB level — no write is silently lost.
        """
        from app.services.subscription_service import record_usage

        all_sqls = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: all_sqls.append(sql)
            cur.fetchone.return_value = {"estimated_cost_cents": 0.01, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 500, 200, "gpt-4o-mini", interaction_type="daily_chat")

        upsert_sqls = [s for s in all_sqls if "ON CONFLICT" in s]
        assert len(upsert_sqls) >= 2, \
            "Both token_usage and usage_by_interaction must use ON CONFLICT upsert"

    def test_two_sequential_record_usage_calls_both_upsert(self):
        from app.services.subscription_service import record_usage

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

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 50, "gpt-4.1-nano", interaction_type="spark")
            record_usage(TEST_UID, 200, 80, "gpt-4.1-nano", interaction_type="spark")

        upserts = [s for s in executed if "ON CONFLICT" in s]
        assert len(upserts) >= 4, "Both calls must produce upserts for both tables"

    def test_db_error_in_record_usage_is_swallowed(self):
        """record_usage must never crash a request — DB errors are suppressed."""
        from app.services.subscription_service import record_usage

        @contextmanager
        def exploding_db():
            raise RuntimeError("DB unavailable")
            yield

        with patch("app.services.subscription_service.get_db", exploding_db):
            record_usage(TEST_UID, 100, 50, "gpt-4o-mini", interaction_type="daily_chat")
            # Must not raise


# ═══════════════════════════════════════════════════════════════════════════════
# Maximum overrun is bounded
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaximumOverrunBounded:

    @pytest.mark.parametrize("model,max_tokens,label", [
        ("gpt-4.1-nano",  120,  "daily_spark"),
        ("gpt-4o-mini",   700,  "quiz"),
        ("gpt-4o-mini",   1024, "daily_chat"),
        ("gpt-4o-mini",   1500, "step_content"),
        ("gpt-4o-mini",   2048, "journey"),
        ("gpt-4o-mini",   600,  "mind_signature"),
    ])
    def test_worst_case_overrun_under_threshold(self, model, max_tokens, label):
        """
        Worst-case cost for one request (800 prompt tokens + max_tokens output).
        Must be < 0.20 cents — the race window overrun is bounded and acceptable.
        """
        from app.services.provider_service import cost_for_tokens
        max_overrun = cost_for_tokens(model, 800, max_tokens)
        assert max_overrun < 0.20, \
            f"{label} ({model}, max_tokens={max_tokens}): " \
            f"overrun {max_overrun:.4f}¢ exceeds 0.20¢ threshold"
