"""SEC-01 / SEC-02 (invariant I2): school students are confined to
STUDENT_ALLOWED_ROUTES.

SEC-01 enumerates app.routes: every route either resolves the caller through
get_signed_in_uid (and is then allowed or denied for students by the
allowlist) or is in PUBLIC_ROUTES. A new route that is neither fails here, so
someone has to decide what a student may do with it.

SEC-02 calls every identity-aware route that isn't allowlisted with a student
token and expects 403 school_student_not_allowed before anything else runs
(no database is configured for these tests, so any DB access would surface as
a 5xx).
"""
import uuid

import pytest

from app.core.auth import get_signed_in_uid
from app.core.school_auth import STUDENT_ALLOWED_ROUTES, api_routes
from tests.schools import identity

STUDENT = "stu_0123456789abcdef"

# Routes that never resolve the caller. Students reach them exactly as an
# anonymous visitor would. Adding one here is a deliberate decision: the route
# must not read the Authorization header by hand.
PUBLIC_ROUTES = {
    ("GET", "/"),
    ("GET", "/sitemap.xml"),
    ("GET", "/api/v1/health"),
    ("GET", "/api/v1/health/db-check"),
    ("GET", "/api/v1/sitemap"),
    ("GET", "/api/v1/geo/country"),
    ("GET", "/api/v1/session/{session_id}"),            # anonymous spark sessions
    ("GET", "/api/v1/mind-signature/verify/{verification_hash}"),
    ("GET", "/api/v1/subscriptions/config"),
    ("GET", "/api/v1/subscriptions/plans"),
    ("POST", "/api/v1/subscriptions/webhook"),           # Stripe-signed
    ("POST", "/api/v1/subscriptions/razorpay/webhook"),  # Razorpay-signed
    ("GET", "/api/v1/notifications/open"),               # email open pixel
    ("GET", "/api/v1/notifications/unsubscribe"),        # HMAC token in the link
    ("GET", "/api/v1/users/consent/confirm"),            # parent's emailed token
    ("POST", "/api/v1/users/consent/confirm"),
    ("POST", "/api/v1/users/consent/report"),
    ("POST", "/api/v1/admin/bootstrap"),                 # only while no admin exists
    ("POST", "/api/v1/school-invites/preview"),          # invite token in the body
    ("GET", "/api/v1/school-login/classes/{code}"),      # student sign-in: class roster
    ("POST", "/api/v1/school-login/sessions"),           # student sign-in: picture / PIN
    ("POST", "/api/v1/school-login/badge"),              # student sign-in: QR badge
}

# Public routes that DO read the Authorization header by hand. Each must reject
# school students itself (tested below).
MANUAL_TOKEN_ROUTES = {
    ("POST", "/api/v1/users/claim"),
}


def _uses_identity(dependant) -> bool:
    return any(dep.call is get_signed_in_uid or _uses_identity(dep) for dep in dependant.dependencies)


def _routes():
    from app.main import app
    return [(method, path, _uses_identity(dependant)) for method, path, _, dependant in api_routes(app)]


ROUTES = _routes()
IDENTITY_ROUTES = {(m, p) for m, p, uses in ROUTES if uses}
ANONYMOUS_ROUTES = {(m, p) for m, p, uses in ROUTES if not uses}
DENIED_ROUTES = sorted(IDENTITY_ROUTES - STUDENT_ALLOWED_ROUTES)


def _fill(path: str) -> str:
    out = path
    while "{" in out:
        start = out.index("{")
        out = out[:start] + str(uuid.uuid4()) + out[out.index("}", start) + 1:]
    return out


@pytest.fixture(autouse=True)
def _no_db_identity(monkeypatch):
    # Firebase uid → users.uid mapping needs the DB; here they are identical.
    monkeypatch.setattr("app.core.auth._map_identity", lambda firebase_uid: firebase_uid)


def test_sec01_allowlisted_routes_exist_and_resolve_the_caller():
    missing = STUDENT_ALLOWED_ROUTES - IDENTITY_ROUTES
    assert not missing, f"allowlisted routes that don't exist or don't resolve the caller: {sorted(missing)}"


def test_sec01_every_route_is_classified():
    unclassified = ANONYMOUS_ROUTES - PUBLIC_ROUTES - MANUAL_TOKEN_ROUTES
    assert not unclassified, (
        f"routes that never resolve the caller: {sorted(unclassified)}. If they are truly public, "
        "add them to PUBLIC_ROUTES; otherwise give them an auth dependency."
    )
    stale = (PUBLIC_ROUTES | MANUAL_TOKEN_ROUTES) - ANONYMOUS_ROUTES
    assert not stale, f"PUBLIC_ROUTES entries that no longer exist or now resolve the caller: {sorted(stale)}"


def test_sec01_school_staff_routes_are_never_student_routes():
    staff = {r for r in STUDENT_ALLOWED_ROUTES if r[1].startswith(("/api/v1/schools", "/api/v1/admin"))}
    assert not staff


@pytest.mark.parametrize("method,path", DENIED_ROUTES, ids=[f"{m} {p}" for m, p in DENIED_ROUTES])
def test_sec02_student_token_is_rejected(client, method, path):
    r = client.request(method, _fill(path), json={}, headers=identity.bearer(STUDENT))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "school_student_not_allowed"


def test_sec02_profile_header_cannot_turn_a_student_into_someone_else(client):
    r = client.get("/api/v1/family/profiles", headers=identity.bearer(STUDENT, x_profile_id="prof_abc"))
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "school_student_not_allowed"


def test_sec02_student_login_cannot_claim_a_family_profile(client):
    r = client.post("/api/v1/users/claim", json={"code": "ABCD2345"}, headers=identity.bearer(STUDENT))
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_login"


def test_sec01_each_allowlisted_endpoint_is_mounted_once():
    # The runtime check matches endpoint functions; a function mounted twice
    # would silently allow its second path too.
    from collections import Counter
    from app.main import app
    endpoints = Counter((m, ep) for m, _, ep, _ in api_routes(app))
    allowed = [(m, ep) for m, p, ep, _ in api_routes(app) if (m, p) in STUDENT_ALLOWED_ROUTES]
    assert all(endpoints[key] == 1 for key in allowed)
