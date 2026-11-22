"""Dev-DB fixture for review.public.spec.ts (F1.3): an adult learner with one finished step due for review.

    backend/.venv/bin/python e2e/review_fixture.py seed <uid> <email> <journey_id>
    backend/.venv/bin/python e2e/review_fixture.py teardown <uid>

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

cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "seed":
    uid, email, jid = args
    step = {"id": "s1", "title": "Why the sky is blue", "type": "concept", "description": "Scattering of light",
            "estimated_minutes": 5}
    q = {"question": "Why does the daytime sky look blue?", "difficulty": "exploratory", "intro_phrase": "Think about sunlight.",
         "concept_tested": "Rayleigh scattering",
         "correct_answer": "Air molecules scatter short (blue) wavelengths of sunlight much more than long ones, so blue light reaches our eyes from every direction.",
         "answer_explanation": "Scattering strength rises steeply as wavelength falls (Rayleigh scattering)."}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (uid, email, display_name, birth_year, age_group_flag, account_status, onboarding_done, "
                        "consent_given_at, consent_version, jurisdiction) VALUES (%s,%s,'E2E Learner',1985,'adult','active',true,now(),'1.0','US') "
                        "ON CONFLICT (uid) DO NOTHING", (uid, email))
            cur.execute("INSERT INTO notification_preferences (uid, email_enabled) VALUES (%s, false) ON CONFLICT (uid) DO NOTHING", (uid,))
            cur.execute("INSERT INTO journeys (id, uid, title, question, description, estimated_hours, steps) "
                        "VALUES (%s,%s,'Light and colour','q','d',1,%s::jsonb)", (jid, uid, json.dumps([step])))
            cur.execute("INSERT INTO quiz_sessions (uid, concept, quiz_data, journey_id, step_id, quiz_set_id, submitted) "
                        "VALUES (%s,'Rayleigh scattering',%s::jsonb,%s,'s1', gen_random_uuid(), true)", (uid, json.dumps(q), jid))
            cur.execute("INSERT INTO review_items (uid, journey_id, step_id, concept, box, due_at) "
                        "VALUES (%s,%s,'s1','Why the sky is blue',1, now() - interval '1 minute')", (uid, jid))
elif cmd == "teardown":
    from app.services.account_service import delete_user_account
    delete_user_account(args[0])
else:
    sys.exit(f"unknown command {cmd}")
print("ok")
