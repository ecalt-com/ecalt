"""Dev-DB fixture for claim-children.public.spec.ts (issue #23).

Seeds an adult parent row for an existing Firebase uid and, optionally, a teen
account whose parent approved through the emailed consent link (a confirmed
parental_consent row and no family_links row). Run with the backend venv:

    backend/.venv/bin/python e2e/claim_children_fixture.py seed <parent_uid> <parent_email> <teen_uid|-> [teen_name]
    backend/.venv/bin/python e2e/claim_children_fixture.py teardown <parent_uid> [teen_uid]

Refuses to run unless the backend .env points at the dev Supabase project.
"""
import os
import secrets
import sys

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

from app.core.config import settings  # noqa: E402
from app.core.database import get_db  # noqa: E402

DEV_PROJECT = "mofngxjdroquxsupgwqk"


def _guard():
    target = f"{getattr(settings, 'DATABASE_URL', '') or ''} {getattr(settings, 'DB_USER', '') or ''}"
    if DEV_PROJECT not in target:
        sys.exit("refusing: backend .env does not point at the dev database")


def seed(parent_uid, parent_email, teen_uid, teen_name):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users (uid, email, display_name, birth_year, age_group_flag,
                                      account_status, onboarding_done, consent_given_at,
                                      consent_version, jurisdiction)
                   VALUES (%s, %s, 'E2E Parent', 1985, 'adult', 'active', true, now(), '1.0', 'US')
                   ON CONFLICT (uid) DO NOTHING""",
                (parent_uid, parent_email),
            )
            if teen_uid != "-":
                cur.execute(
                    """INSERT INTO users (uid, email, display_name, birth_year, age_group_flag,
                                          account_status, onboarding_done, consent_given_at,
                                          consent_version, jurisdiction)
                       VALUES (%s, NULL, %s, 2011, 'teen', 'active', true, now(), '1.0', 'US')""",
                    (teen_uid, teen_name),
                )
                cur.execute(
                    """INSERT INTO parental_consent (token, uid, parent_email, confirmed_at,
                                                     expires_at, status)
                       VALUES (%s, %s, %s, now(), now() + interval '7 days', 'confirmed')""",
                    (secrets.token_urlsafe(24), teen_uid, parent_email),
                )


def teardown(parent_uid, teen_uid):
    # The app's own erasure cascade: consent_events is append-only, so it
    # pseudonymizes those rows and deletes everything else.
    from app.services.account_service import delete_user_account
    for uid in (teen_uid, parent_uid):
        if uid:
            delete_user_account(uid)


if __name__ == "__main__":
    _guard()
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "seed":
        seed(args[0], args[1], args[2], args[3] if len(args) > 3 else "E2E Teen")
    elif cmd == "teardown":
        teardown(args[0], args[1] if len(args) > 1 else None)
    else:
        sys.exit(f"unknown command {cmd}")
    print("ok")
