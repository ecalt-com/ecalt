"""School AI-budget alert emails at 80% / 100% (SC-504).

The threshold crossing is detected inside the usage-recording transaction, so
the per-month dedup is atomic; only school owners/admins are emailed, and only
the highest threshold just crossed fires. Delivery itself is a thin seam we
capture here instead of sending mail.
"""
from datetime import date

import pytest
from psycopg2.extras import RealDictCursor

from app.services import subscription_service as ss
from tests.factories import schools as f

pytestmark = pytest.mark.schools_db

PERIOD = date.today().replace(day=1)


def _seed_usage(db, school_id, cost):
    f.fetch(db, """INSERT INTO school_usage (school_id, period_start, cost_cents, input_tokens, output_tokens)
                   VALUES (%s, %s, %s, 0, 0)
                   ON CONFLICT (school_id, period_start) DO UPDATE SET cost_cents = EXCLUDED.cost_cents""",
            (school_id, PERIOD, cost))


def _alerts(db, school_id, total):
    with db.cursor(cursor_factory=RealDictCursor) as cur:
        return ss._school_budget_alerts(cur, school_id, PERIOD, total)


def _markers(db, school_id):
    r = f.fetch(db, "SELECT alert_80_at, alert_100_at FROM school_usage WHERE school_id = %s AND period_start = %s",
                (school_id, PERIOD))[0]
    return bool(r["alert_80_at"]), bool(r["alert_100_at"])


def test_crossing_80_then_100_fires_once_each(db):
    school = f.make_school(db, budget_cents=1000)
    f.make_staff(db, school, role="owner", email="owner@school.test")
    f.make_staff(db, school, role="admin", email="admin@school.test")
    f.make_staff(db, school, role="teacher", email="teacher@school.test")
    _seed_usage(db, school["id"], 850)

    a = _alerts(db, school["id"], 850)              # 85%
    assert [x["percent"] for x in a] == [80]
    emails = {e for x in a for (_uid, e) in x["recipients"]}
    assert {"owner@school.test", "admin@school.test"} <= emails     # admins notified
    assert "teacher@school.test" not in emails                      # teachers are not
    assert _markers(db, school["id"]) == (True, False)

    assert _alerts(db, school["id"], 900) == []     # still 90%, 80 already alerted (dedup)

    b = _alerts(db, school["id"], 1000)             # 100%
    assert [x["percent"] for x in b] == [100]
    assert _markers(db, school["id"]) == (True, True)

    assert _alerts(db, school["id"], 1200) == []    # dedup — no re-fire over budget


def test_jump_straight_past_both_fires_only_100(db):
    school = f.make_school(db, budget_cents=1000)
    f.make_staff(db, school, role="owner", email="o2@school.test")
    _seed_usage(db, school["id"], 1500)

    a = _alerts(db, school["id"], 1500)             # 150% in one accrual
    assert [x["percent"] for x in a] == [100]
    # the 80 marker is stamped too, so it can never fire afterwards
    assert _markers(db, school["id"]) == (True, True)


def test_below_80_no_alert(db):
    school = f.make_school(db, budget_cents=1000)
    f.make_staff(db, school, role="owner", email="o3@school.test")
    _seed_usage(db, school["id"], 500)
    assert _alerts(db, school["id"], 500) == []
    assert _markers(db, school["id"]) == (False, False)


def test_no_budget_no_alert(db):
    school = f.make_school(db, budget_cents=0)
    f.make_staff(db, school, role="owner", email="o4@school.test")
    _seed_usage(db, school["id"], 500)
    assert _alerts(db, school["id"], 500) == []


def test_record_school_usage_wires_through_to_delivery(db, monkeypatch):
    captured = []
    monkeypatch.setattr(ss, "_send_budget_alerts", lambda alerts: captured.append(alerts))
    cost = ss.cost_for_tokens("gpt-4o-mini", 0, 100_000)
    school = f.make_school(db, budget_cents=cost / 0.85)   # one call lands at ~85%
    f.make_staff(db, school, role="owner", email="o5@school.test")

    ss.record_school_usage(school["id"], 0, 100_000, "gpt-4o-mini")

    assert captured and captured[-1] and captured[-1][0]["percent"] == 80
    assert ("o5@school.test") in {e for (_uid, e) in captured[-1][0]["recipients"]}
