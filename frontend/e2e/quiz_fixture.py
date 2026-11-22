"""Dev-DB fixture for quiz-lazy.public.spec.ts (F1.1/F1.2): an adult learner, a one-step journey with cached lesson content.

    backend/.venv/bin/python e2e/quiz_fixture.py seed <uid> <email> <journey_id> [language]
    backend/.venv/bin/python e2e/quiz_fixture.py counts <uid> <journey_id>   # JSON: events by name, quiz sets, quiz sessions
    backend/.venv/bin/python e2e/quiz_fixture.py teardown <uid>

Refuses to run unless the backend .env points at the dev Supabase project.
"""
import json
import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend")
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

from app.core.config import settings  # noqa: E402
from app.core.database import get_db  # noqa: E402

if "mofngxjdroquxsupgwqk" not in f"{settings.DATABASE_URL} {settings.DB_USER}":
    sys.exit("refusing: backend .env does not point at the dev database")

LESSON = "## Why the sky is blue\n\n" + "\n\n".join(
    f"Sunlight looks white but is a mix of every colour. Paragraph {i}: air molecules scatter short, blue wavelengths far more strongly "
    "than long, red ones, a effect called Rayleigh scattering, so blue light reaches your eyes from every direction of the sky."
    for i in range(1, 9))

cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "seed":
    uid, email, jid = args[:3]
    language = args[3] if len(args) > 3 else 'en'
    step = {"id": "s1", "title": "Why the sky is blue", "type": "concept", "description": "Scattering of light",
            "estimated_minutes": 5}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (uid, email, display_name, birth_year, age_group_flag, account_status, onboarding_done, "
                        "consent_given_at, consent_version, jurisdiction) VALUES (%s,%s,'E2E Learner',1985,'adult','active',true,now(),'1.0','US') "
                        "ON CONFLICT (uid) DO NOTHING", (uid, email))
            cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                        "VALUES (%s,%s,'Light and colour','q','d',1,%s::jsonb)", (jid, uid, json.dumps([step])))
            if language != "en":
                cur.execute("UPDATE journeys SET language = %s WHERE id = %s", (language, jid))
    from app.services.ai_service import upsert_step_content
    upsert_step_content(jid, "s1", LESSON, [], "e2e", overwrite=True)
elif cmd == "counts":
    uid, jid = args
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT event, count(*) AS n FROM learning_events WHERE uid = %s GROUP BY 1", (uid,))
            events = {r["event"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT count(DISTINCT quiz_set_id) AS sets, count(*) AS sessions FROM quiz_sessions WHERE uid = %s AND journey_id = %s", (uid, jid))
            q = dict(cur.fetchone())
    print(json.dumps({"events": events, **q}))
    sys.exit(0)
elif cmd == "teardown":
    from app.services.account_service import delete_user_account
    delete_user_account(args[0])
else:
    sys.exit(f"unknown command {cmd}")
print("ok")
