"""F2.4: marketplace search and sort. Real SQL."""
import pytest

from app.api.v1.endpoints.journeys import _search_terms

pytestmark = pytest.mark.schools_db


def _journey(db, jid, title, desc="d", tags=(), status="published", likes=0, pop=0, school=None, age=0):
    with db.cursor() as cur:
        cur.execute("INSERT INTO users (uid, email) VALUES ('owner','o@x.com') ON CONFLICT DO NOTHING")
        cur.execute(
            "INSERT INTO journeys (id, uid, title, question, description, estimated_hours, tags, marketplace_status, "
            "like_count, popularity_score, school_id, created_at) "
            "VALUES (%s,'owner',%s,'q',%s,1,%s,%s,%s,%s,%s, now() - make_interval(days => %s))",
            (jid, title, desc, list(tags), status, likes, pop, school, age))


def _ids(client, **params):
    r = client.get("/api/v1/journeys/marketplace", params=params)
    assert r.status_code == 200, r.text
    return [j["id"] for j in r.json()["journeys"]], r.json()["total"]


@pytest.fixture
def shelf(db):
    _journey(db, "a", "How black holes work", "Gravity and light", ["physics"], pop=5, likes=1, age=3)
    _journey(db, "b", "Baking sourdough", "Flour, water, patience", ["cooking", "chemistry"], pop=9, likes=7, age=2)
    _journey(db, "c", "100% juice or not?", "Reading labels", ["nutrition"], pop=1, likes=3, age=1)
    _journey(db, "d", "Private black hole notes", "x", [], status="private")
    return db


def test_terms_are_escaped_and_capped():
    assert _search_terms("100% a_b") == ["100\\%", "a\\_b"]
    assert _search_terms("  ") == [] and _search_terms(None) == []
    assert len(_search_terms("a b c d e f g")) == 5 and len(_search_terms("x" * 80)[0]) == 50


def test_search_matches_title_description_and_tags_case_insensitively(client, shelf):
    assert _ids(client, q="BLACK holes")[0] == ["a"]
    assert _ids(client, q="gravity")[0] == ["a"]                 # description
    assert _ids(client, q="chem")[0] == ["b"]                    # tag
    assert _ids(client, q="black sourdough")[0] == []           # every word must match one journey


def test_wildcards_match_literally(client, shelf):
    assert _ids(client, q="100%")[0] == ["c"]
    assert _ids(client, q="%")[0] == ["c"]                       # only the journey that contains a '%'
    assert _ids(client, q="_")[0] == []


def test_only_published_non_school_journeys_are_searchable(client, shelf):
    assert "d" not in _ids(client, q="black")[0]
    assert _ids(client)[1] == 3


def test_sorts(client, shelf):
    assert _ids(client)[0] == ["b", "a", "c"]                    # popular (default)
    assert _ids(client, sort="popular")[0] == ["b", "a", "c"]
    assert _ids(client, sort="liked")[0] == ["b", "c", "a"]
    assert _ids(client, sort="new")[0] == ["c", "b", "a"]
    assert client.get("/api/v1/journeys/marketplace", params={"sort": "id; DROP TABLE journeys"}).status_code == 422


def test_search_combines_with_filters_and_paging(client, shelf):
    assert _ids(client, q="o", limit=2, offset=0)[1] == 3
    assert len(_ids(client, q="o", limit=2, offset=0)[0]) == 2
    assert len(_ids(client, q="o", limit=2, offset=2)[0]) == 1
