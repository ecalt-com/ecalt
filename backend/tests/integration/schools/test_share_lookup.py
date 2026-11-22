"""F1.6: only ordinary account-owned journeys expose their title on the public card. Real SQL."""
import pytest

from app.api.v1.endpoints import share

pytestmark = pytest.mark.schools_db


def _journey(db, jid, uid, profile_type="account", school_id=None):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email, profile_type) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (uid, f"{uid}@x.com" if profile_type == "account" else None, profile_type))
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, school_id) "
                    "VALUES (%s, %s, 'Black holes', 'q', 'about them', 1, %s)", (jid, uid, school_id))


def test_ordinary_journey_shows_its_title(db):
    _journey(db, "j1", "u1")
    assert share._lookup("j1")["title"] == "Black holes"
    assert "Black holes — ECALT" in share.render_card("j1", share._lookup("j1"))


def test_child_profile_journeys_get_the_generic_card(db):
    _journey(db, "j2", "prof_abc", profile_type="profile")
    assert share._lookup("j2") == {"generic": True}
    assert "Black holes" not in share.render_card("j2", share._lookup("j2"))


def test_unknown_journey_is_none(db):
    assert share._lookup("nope") is None
