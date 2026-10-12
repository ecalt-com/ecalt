"""UNIT-AUTH-*: pure pieces of core/school_auth.py and school settings."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.school_auth import enforce_student_route, is_school_student_uid, uuid_or_404
from app.services.school_service import SchoolSettings, effective_settings


@pytest.mark.parametrize("uid,expected", [
    ("stu_ab12", True), ("prof_ab12", False), ("Xy9StuAbc", False), ("", False), (None, False),
])
def test_student_uid_prefix(uid, expected):
    assert is_school_student_uid(uid) is expected


def _request(method, path):
    """A request whose matched endpoint is the app's endpoint for path."""
    from app.core.school_auth import api_routes
    from app.main import app
    endpoint = next((ep for m, p, ep, _ in api_routes(app) if p == path and m in (method, "GET")), None)
    return SimpleNamespace(method=method, app=app, scope={"endpoint": endpoint} if endpoint else {})


def test_allowlist_allows_listed_routes_and_treats_head_as_get():
    enforce_student_route(_request("GET", "/api/v1/journeys/{journey_id}"))
    enforce_student_route(_request("HEAD", "/api/v1/journeys/{journey_id}"))


@pytest.mark.parametrize("method,path", [
    ("DELETE", "/api/v1/journeys/{journey_id}"),        # listed path, unlisted method
    ("GET", "/api/v1/explore"),
    ("GET", None),                                       # route unknown → fail closed
])
def test_allowlist_denies_everything_else(method, path):
    with pytest.raises(HTTPException) as exc:
        enforce_student_route(_request(method, path))
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "school_student_not_allowed"


def test_uuid_or_404():
    assert uuid_or_404("6F9619FF-8B86-D011-B42D-00C04FC964FF") == "6f9619ff-8b86-d011-b42d-00c04fc964ff"
    with pytest.raises(HTTPException) as exc:
        uuid_or_404("1; DROP TABLE schools", "class_not_found")
    assert exc.value.status_code == 404 and exc.value.detail["error"] == "class_not_found"


def test_settings_defaults_and_validation():
    assert effective_settings(None) == SchoolSettings().model_dump()
    # keys from an older version are ignored rather than breaking reads
    assert effective_settings({"retired_key": 1, "login_roster_visible": False})["login_roster_visible"] is False
    with pytest.raises(ValueError):
        SchoolSettings(unknown=True)
