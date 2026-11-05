"""G4: error reports must not carry student data or credentials."""
import sentry_sdk

from app.core.sentry_scrub import init_options, scrub_breadcrumb, scrub_event

SID = "1b48bd4b-60d9-43ed-a569-f80147c760c4"


def test_init_options_are_accepted_by_the_sdk():
    opts = init_options()
    assert opts["send_default_pii"] is False and opts["max_request_body_size"] == "never"
    assert opts["include_local_variables"] is False
    sentry_sdk.init(dsn=None, **opts)  # raises on an unknown option


def test_scrub_event_removes_personal_data_and_tags_school():
    event = {
        "request": {
            "url": f"https://api.example/api/v1/schools/{SID}/students/stu_ab12cd?name=Asha",
            "query_string": "name=Asha", "data": {"display_name": "Asha K"}, "cookies": {"a": "b"},
            "headers": {"Authorization": "Bearer x", "X-Parent-Unlock": "u", "X-Forwarded-For": "1.2.3.4",
                        "Accept": "application/json"},
        },
        "user": {"id": "stu_ab12cd", "ip_address": "1.2.3.4"},
        "message": "failed for stu_ab12cd (parent@example.com)",
        "logentry": {"message": "uid %s", "params": ["stu_ab12cd"]},
        "exception": {"values": [{"type": "ValueError", "value": "bad student stu_ab12cd"}]},
        "breadcrumbs": {"values": [{"message": "GET stu_ab12cd", "data": {"url": "https://x/y?token=t#frag"}}]},
        "transaction": "/api/v1/school-student/stu_ab12cd",
    }
    out = scrub_event(event)
    req = out["request"]
    assert req["url"] == f"https://api.example/api/v1/schools/{SID}/students/stu_[redacted]"
    assert "query_string" not in req and "data" not in req and "cookies" not in req
    assert req["headers"] == {"Accept": "application/json"}
    assert "user" not in out
    assert out["tags"]["school_id"] == SID
    flat = repr(out)
    assert "stu_ab12cd" not in flat and "parent@example.com" not in flat and "token=t" not in flat


def test_breadcrumb_query_is_dropped():
    crumb = scrub_breadcrumb({"data": {"url": "https://x/a?b=1", "http.query": "b=1"}})
    assert crumb["data"] == {"url": "https://x/a", "http.query": None}
