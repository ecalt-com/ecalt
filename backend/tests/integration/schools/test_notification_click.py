"""F1.4: the click endpoint stamps the log row once and redirects safely. Real SQL."""
from urllib.parse import parse_qs, urlparse

import pytest

from app.services import notification_links as nl

pytestmark = pytest.mark.schools_db


def _log(db):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES ('u1', 'u1@x.com') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO notification_log (uid, notification_type, channel) "
                    "VALUES ('u1', 'daily_spark', 'email') RETURNING id")
        return str(cur.fetchone()[0])


def _path(url):
    u = urlparse(url)
    return u.path + "?" + u.query


def test_click_stamps_once_redirects_with_utm_and_records_an_event(client, db):
    log_id = _log(db)
    url = _path(nl.build_click_url(log_id, "/journey/j1#step-s2"))
    r = client.get(url, follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.endswith("#step-s2") and "utm_source=notif" in loc and "utm_campaign=daily_spark" in loc
    with db.cursor() as cur:
        cur.execute("SELECT clicked_at, opened_at FROM notification_log WHERE id = %s", (log_id,))
        first, opened = cur.fetchone()
        assert first is not None and opened is not None
        client.get(url, follow_redirects=False)
        cur.execute("SELECT clicked_at FROM notification_log WHERE id = %s", (log_id,))
        assert cur.fetchone()[0] == first
        cur.execute("SELECT count(*) FROM learning_events WHERE event = 'notification_click'")
        assert cur.fetchone()[0] == 2


def test_tampered_or_unsafe_links_are_refused(client, db):
    log_id = _log(db)
    q = parse_qs(urlparse(nl.build_click_url(log_id, "/learn")).query)
    assert client.get(f"/api/v1/notifications/c/{log_id}?to=%2Flearn&sig=bad", follow_redirects=False).status_code == 400
    evil = "//evil.com"
    sig = nl.sign_click(log_id, evil)
    r = client.get(f"/api/v1/notifications/c/{log_id}?to=%2F%2Fevil.com&sig={sig}", follow_redirects=False)
    assert r.status_code == 400 and "location" not in r.headers
    with db.cursor() as cur:
        cur.execute("SELECT clicked_at FROM notification_log WHERE id = %s", (log_id,))
        assert cur.fetchone()[0] is None
    assert q["sig"][0]


def test_a_valid_link_for_a_missing_row_still_redirects(client, db):
    url = _path(nl.build_click_url("00000000-0000-0000-0000-000000000000", "/learn"))
    assert client.get(url, follow_redirects=False).status_code == 302
