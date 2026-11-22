"""F0.1: the notification queue can't flood or starve. Real SQL (migration 020)."""
import asyncio
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import scheduler as sch
from app.services.notification_service import (
    BLOCKED, DEFERRED, FAILED, SENT, SendOutcome, notification_service,
)

pytestmark = pytest.mark.schools_db

NOW = lambda: datetime.now(timezone.utc)  # noqa: E731


def _user(db, uid, email=True):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email, display_name) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (uid, f"{uid}@example.com" if email else None, uid))


def _row(db, uid, ntype="cliffhanger_return", status="pending", due=None, channel="email", **kw):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO notification_queue (uid, notification_type, channel, scheduled_for, status, payload, expires_at) "
            "VALUES (%s,%s,%s,%s,%s,'{}',%s) RETURNING id",
            (uid, ntype, channel, due or NOW() - timedelta(minutes=1), status, kw.get("expires_at")))
        return str(cur.fetchone()[0])


def _status(db, rid):
    with db.cursor() as cur:
        cur.execute("SELECT status, attempts, scheduled_for FROM notification_queue WHERE id = %s", (rid,))
        return cur.fetchone()


def _run(db, monkeypatch, outcome_for):
    sent = []

    async def fake(uid, email, notification_type, channel, context):
        sent.append((uid, notification_type))
        return outcome_for(uid, notification_type)

    monkeypatch.setattr(notification_service, "attempt_send", fake)
    asyncio.run(sch._queue_processor())
    return sent


def test_quiet_hours_move_the_same_row_and_never_add_one(db, monkeypatch):
    _user(db, "u1")
    rid = _row(db, "u1")
    later = NOW() + timedelta(hours=2)
    _run(db, monkeypatch, lambda u, t: SendOutcome(DEFERRED, retry_at=later))
    st, attempts, when = _status(db, rid)
    assert st == "pending" and abs((when - later).total_seconds()) < 2
    with db.cursor() as cur:
        cur.execute("SELECT count(*) FROM notification_queue")
        assert cur.fetchone()[0] == 1


def test_blocked_cliffhanger_expires_but_a_digest_retries_then_expires(db, monkeypatch):
    _user(db, "u1")
    cliff = _row(db, "u1")
    digest = _row(db, "u1", "weekly_digest")
    _run(db, monkeypatch, lambda u, t: SendOutcome(BLOCKED, reason="cap"))
    # at most 2 due rows per user per run: both were taken
    assert _status(db, cliff)[0] == "expired"
    st, attempts, when = _status(db, digest)
    assert (st, attempts) == ("pending", 1) and when > NOW() + timedelta(hours=20)
    for _ in range(2):
        with db.cursor() as cur:
            cur.execute("UPDATE notification_queue SET scheduled_for = now() - interval '1 minute' WHERE id = %s", (digest,))
        _run(db, monkeypatch, lambda u, t: SendOutcome(BLOCKED, reason="cap"))
    assert _status(db, digest)[0] == "expired"


def test_failed_send_backs_off_then_gives_up(db, monkeypatch):
    _user(db, "u1")
    rid = _row(db, "u1", "weekly_digest")
    for expected_attempts in (1, 2, 3):
        _run(db, monkeypatch, lambda u, t: SendOutcome(FAILED))
        st, attempts, _ = _status(db, rid)
        assert (st, attempts) == ("pending", expected_attempts)
        with db.cursor() as cur:
            cur.execute("UPDATE notification_queue SET scheduled_for = now() - interval '1 minute' WHERE id = %s", (rid,))
    _run(db, monkeypatch, lambda u, t: SendOutcome(FAILED))
    assert _status(db, rid)[0] == "failed"


def test_one_users_backlog_does_not_starve_another(db, monkeypatch):
    _user(db, "noisy"); _user(db, "quiet")
    for i in range(200):
        _row(db, "noisy", "daily_spark", due=NOW() - timedelta(days=100, minutes=i))  # outside the unique index
    quiet = _row(db, "quiet", "weekly_digest", due=NOW() - timedelta(minutes=1))
    sent = _run(db, monkeypatch, lambda u, t: SendOutcome(SENT))
    assert ("quiet", "weekly_digest") in sent
    assert sum(1 for u, _ in sent if u == "noisy") <= sch.MAX_DUE_PER_USER_PER_RUN
    assert _status(db, quiet)[0] == "sent"


def test_unique_index_rejects_a_second_pending_cliffhanger(db):
    _user(db, "u1")
    _row(db, "u1")
    with db.cursor() as cur:
        cur.execute("INSERT INTO notification_queue (uid, notification_type, channel, scheduled_for) "
                    "VALUES ('u1','cliffhanger_return','email',now()) ON CONFLICT DO NOTHING")
        cur.execute("SELECT count(*) FROM notification_queue WHERE uid='u1'")
        assert cur.fetchone()[0] == 1
        # a finished row doesn't block the next one
        cur.execute("UPDATE notification_queue SET status='sent' WHERE uid='u1'")
        cur.execute("INSERT INTO notification_queue (uid, notification_type, channel, scheduled_for) "
                    "VALUES ('u1','cliffhanger_return','email',now())")


def test_expired_rows_are_never_sent_and_abandoned_claims_fail(db, monkeypatch):
    _user(db, "u1")
    old = _row(db, "u1", expires_at=NOW() - timedelta(hours=1))
    stuck = _row(db, "u1", "weekly_digest", status="sending")
    with db.cursor() as cur:
        cur.execute("UPDATE notification_queue SET claimed_at = now() - interval '2 hours' WHERE id = %s", (stuck,))
    sent = _run(db, monkeypatch, lambda u, t: SendOutcome(SENT))
    assert sent == []
    assert _status(db, old)[0] == "expired"
    assert _status(db, stuck)[0] == "failed"


def test_a_row_whose_final_update_fails_is_not_sent_again(db, monkeypatch):
    _user(db, "u1")
    rid = _row(db, "u1", "weekly_digest")

    def boom(cur, row, outcome):
        raise RuntimeError("db hiccup after delivery")

    monkeypatch.setattr(sch, "_resolve_row", boom)
    first = _run(db, monkeypatch, lambda u, t: SendOutcome(SENT))
    assert first == [("u1", "weekly_digest")]
    assert _status(db, rid)[0] == "sending"          # claimed, never back to pending
    second = _run(db, monkeypatch, lambda u, t: SendOutcome(SENT))
    assert second == []


def test_migration_020_is_idempotent_and_cleans_old_rows(db):
    sql = (pathlib.Path(__file__).resolve().parents[4] / "migrations" / "020_notification_queue_hardening.sql").read_text()
    _user(db, "u1")
    with db.cursor() as cur:
        cur.execute("DROP INDEX IF EXISTS notification_queue_one_pending")
        for i in range(3):
            cur.execute("INSERT INTO notification_queue (uid, notification_type, channel, scheduled_for, created_at) "
                        "VALUES ('u1','weekly_digest','email',now(), now() - make_interval(hours => %s))", (i,))
        cur.execute("INSERT INTO notification_queue (uid, notification_type, channel, scheduled_for, created_at, status) "
                    "VALUES ('u1','weekly_digest','email',now(), now() - interval '90 days', 'sent')")
        cur.execute(sql)
        cur.execute(sql)
        cur.execute("SELECT status, count(*) FROM notification_queue GROUP BY 1 ORDER BY 1")
        assert dict(cur.fetchall()) == {"expired": 2, "pending": 1}
