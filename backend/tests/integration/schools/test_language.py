"""F2.2: language storage, lookups, the preference endpoint, explore and fork. Real SQL."""
import json
from datetime import date

import pytest

from app.api.v1.endpoints import explore as explore_ep
from app.models.schemas import Journey, JourneyStep
from app.services import language_service as ls
from tests.schools.identity import bearer

pytestmark = pytest.mark.schools_db


def _user(db, uid, age="adult", lang="en"):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email, age_group_flag, account_status, preferred_language) "
                    "VALUES (%s, %s, %s, 'active', %s) ON CONFLICT (uid) DO UPDATE SET preferred_language = EXCLUDED.preferred_language, "
                    "age_group_flag = EXCLUDED.age_group_flag", (uid, f"{uid}@x.com", age, lang))


def _journey(db, jid, uid, lang="en", status="private"):
    with db.cursor() as cur:
        cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps, language, marketplace_status) "
                    "VALUES (%s,%s,'T','q','d',1,%s::jsonb,%s,%s)",
                    (jid, uid, json.dumps([{"id": "s1", "title": "S", "description": "d", "type": "concept", "estimated_minutes": 5}]),
                     lang, status))


def test_lookups_and_their_fallbacks(db):
    _user(db, "u1", lang="hi")
    _journey(db, "j1", "u1", lang="hi")
    assert ls.user_language("u1") == "hi" and ls.journey_language("j1") == "hi"
    assert ls.user_language("nobody") == "en" and ls.journey_language("nope") == "en"
    assert ls.user_language(None) == "en" and ls.journey_language(None) == "en"
    with db.cursor() as cur:
        cur.execute("INSERT INTO quiz_sessions (uid, concept, quiz_data, journey_id, step_id) "
                    "VALUES ('u1','c','{}'::jsonb,'j1','s1') RETURNING id")
        qid = str(cur.fetchone()[0])
    assert ls.quiz_language(qid, "u1") == "hi"
    assert ls.quiz_language(qid, "someone-else") == "en"          # not their quiz: their own preference (English)
    assert ls.for_journey_or_user("j1", "u1") == "hi" and ls.for_journey_or_user(None, "u1") == "hi"


def test_non_english_is_for_adult_accounts_only(db):
    _user(db, "adult", "adult"); _user(db, "teen", "teen"); _user(db, "kid", "child")
    assert [ls.allowed_language(u, "hi") for u in ("adult", "teen", "kid", None)] == ["hi", "en", "en", "en"]
    assert ls.allowed_language("teen", "en") == "en" and ls.allowed_language("adult", "xx") == "en"


def test_preference_endpoint(client, db):
    _user(db, "adult", "adult"); _user(db, "teen", "teen")
    h = bearer("adult")
    r = client.patch("/api/v1/users/me/language", json={"language": "HI"}, headers=h)
    assert r.status_code == 200 and r.json()["preferred_language"] == "hi"
    assert client.get("/api/v1/users/me", headers=h).json()["preferred_language"] == "hi"
    assert client.patch("/api/v1/users/me/language", json={"language": "en"}, headers=h).json()["preferred_language"] == "en"
    assert client.patch("/api/v1/users/me/language", json={"language": "tlh"}, headers=h).status_code == 422
    t = client.patch("/api/v1/users/me/language", json={"language": "hi"}, headers=bearer("teen"))
    assert t.status_code == 403 and t.json()["detail"]["error"] == "language_not_available"
    assert client.patch("/api/v1/users/me/language", json={"language": "en"}, headers=bearer("teen")).status_code == 200


def _fake_journey(language):
    return Journey(id="gen-1", question="q", title="शीर्षक", description="d", estimated_hours=1, tags=["t"], icon="x",
                   steps=[JourneyStep(id="s1", title="S", description="d", type="concept", estimated_minutes=5)],
                   language=language)


def test_preview_then_confirm_stores_the_journeys_language(client, db, monkeypatch):
    _user(db, "adult", "adult", lang="hi")
    seen = {}

    async def fake_generate(**kw):
        seen.update(kw)
        return _fake_journey(kw["language"]), 10, 10

    monkeypatch.setattr(explore_ep, "generate_journey", fake_generate)
    monkeypatch.setattr(explore_ep, "check_budget", lambda uid: (True, "ok"))
    monkeypatch.setattr(explore_ep, "record_usage", lambda *a, **k: None)
    async def no_warm(*a, **k): return None
    monkeypatch.setattr(explore_ep, "warm_journey_steps", no_warm)
    monkeypatch.setattr(explore_ep, "generate_and_attach_hero", no_warm)
    h = bearer("adult")

    preview = client.post("/api/v1/explore/preview", json={"question": "ब्लैक होल क्या है?"}, headers=h)
    assert preview.status_code == 200, preview.text
    assert seen["language"] == "hi" and preview.json()["journey"]["language"] == "hi"      # from the learner's preference
    confirm = client.post("/api/v1/explore/confirm", json={"preview_token": preview.json()["preview_token"]}, headers=h)
    assert confirm.status_code == 200 and confirm.json()["journey"]["language"] == "hi"
    with db.cursor() as cur:
        cur.execute("SELECT language FROM journeys WHERE id = 'gen-1'")
        assert cur.fetchone()[0] == "hi"

    # an explicit request language wins over the preference; unknown codes become English
    client.post("/api/v1/explore/preview", json={"question": "q", "language": "en"}, headers=h)
    assert seen["language"] == "en"
    client.post("/api/v1/explore/preview", json={"question": "q", "language": "zz"}, headers=h)
    assert seen["language"] == "en"


def test_minors_are_always_given_english(client, db, monkeypatch):
    _user(db, "teen", "teen", lang="hi")                     # e.g. an account that was changed some other way
    seen = {}

    async def fake_generate(**kw):
        seen.update(kw)
        return _fake_journey(kw["language"]), 1, 1

    monkeypatch.setattr(explore_ep, "generate_journey", fake_generate)
    monkeypatch.setattr(explore_ep, "check_budget", lambda uid: (True, "ok"))
    monkeypatch.setattr(explore_ep, "record_usage", lambda *a, **k: None)
    r = client.post("/api/v1/explore/preview", json={"question": "q", "language": "hi"}, headers=bearer("teen"))
    assert r.status_code == 200 and seen["language"] == "en"


def test_fork_keeps_the_source_language(client, db):
    _user(db, "owner", "adult"); _user(db, "reader", "adult")
    _journey(db, "pub", "owner", lang="hi", status="published")
    r = client.post("/api/v1/journeys/pub/fork", headers=bearer("reader"))
    assert r.status_code in (200, 201), r.text
    new_id = r.json()["journey"]["id"]
    assert r.json()["journey"]["language"] == "hi"
    with db.cursor() as cur:
        cur.execute("SELECT language FROM journeys WHERE id = %s", (new_id,))
        assert cur.fetchone()[0] == "hi"


def test_english_journeys_never_reference_the_new_column(client, db, monkeypatch):
    """So the code is safe to deploy before migration 025: with English, no UPDATE of language runs."""
    _user(db, "adult", "adult")
    statements = []
    from app.core import database
    real = database.get_db

    async def fake_generate(**kw):
        return _fake_journey("en"), 1, 1

    monkeypatch.setattr(explore_ep, "generate_journey", fake_generate)
    monkeypatch.setattr(explore_ep, "check_budget", lambda uid: (True, "ok"))
    monkeypatch.setattr(explore_ep, "record_usage", lambda *a, **k: None)
    preview = client.post("/api/v1/explore/preview", json={"question": "q"}, headers=bearer("adult"))
    import psycopg2.extras
    orig = psycopg2.extras.RealDictCursor.execute
    monkeypatch.setattr(psycopg2.extras.RealDictCursor, "execute",
                        lambda self, q, a=None: (statements.append(str(q)), orig(self, q, a))[1])
    async def no_warm(*a, **k): return None
    monkeypatch.setattr(explore_ep, "warm_journey_steps", no_warm)
    monkeypatch.setattr(explore_ep, "generate_and_attach_hero", no_warm)
    client.post("/api/v1/explore/confirm", json={"preview_token": preview.json()["preview_token"]}, headers=bearer("adult"))
    assert statements and not any("SET language" in s for s in statements)
