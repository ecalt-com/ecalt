"""
Unit tests for the marketplace popularity scan job (app/services/scheduler.py).

The job must never raise (it runs unattended on a cron trigger) and should
issue exactly two statements: recompute popularity_score, then promote
still-private journeys that cross the popularity bar into pending_review.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.services.scheduler import _marketplace_popularity_scan


@pytest.mark.asyncio
async def test_scan_runs_two_statements():
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = MagicMock(return_value=False)
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def get_db():
        yield conn

    with patch("app.core.database.get_db", get_db):
        await _marketplace_popularity_scan()

    assert cur.execute.call_count == 2
    score_sql = cur.execute.call_args_list[0][0][0]
    promote_sql = cur.execute.call_args_list[1][0][0]
    assert "popularity_score" in score_sql
    assert "pending_review" in promote_sql
    assert "'published'" not in promote_sql  # must never touch already-decided rows
    assert "'rejected'" not in promote_sql


@pytest.mark.asyncio
async def test_scan_never_raises_on_db_error():
    @contextmanager
    def get_db():
        raise RuntimeError("db unavailable")
        yield  # pragma: no cover

    with patch("app.core.database.get_db", get_db):
        await _marketplace_popularity_scan()  # must not propagate
