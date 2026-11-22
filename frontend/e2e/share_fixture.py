"""Dev-DB fixture for share-preview.public.spec.ts (F1.6): one journey owned by a throwaway user.

    backend/.venv/bin/python e2e/share_fixture.py seed <uid> <journey_id> <title>
    backend/.venv/bin/python e2e/share_fixture.py teardown <uid>

Refuses to run unless the backend .env points at the dev Supabase project.
"""
import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

from app.core.config import settings  # noqa: E402
from app.core.database import get_db  # noqa: E402

if "mofngxjdroquxsupgwqk" not in f"{settings.DATABASE_URL} {settings.DB_USER}":
    sys.exit("refusing: backend .env does not point at the dev database")

cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "seed":
    uid, jid, title = args
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (uid, email, display_name) VALUES (%s, %s, 'E2E Share') ON CONFLICT DO NOTHING",
                        (uid, f"{uid}@example.com"))
            cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                        "VALUES (%s, %s, %s, 'q', 'A journey used by an end-to-end test.', 1, '[]'::jsonb)",
                        (jid, uid, title))
elif cmd == "teardown":
    from app.services.account_service import delete_user_account
    delete_user_account(args[0])
else:
    sys.exit(f"unknown command {cmd}")
print("ok")
