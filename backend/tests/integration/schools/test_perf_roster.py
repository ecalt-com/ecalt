"""PERF-03 (SC-802): a 2,000-row roster import commits in one transaction
in under 30 s (local Postgres; network adds little — it's one transaction)."""
import time

import pytest

from tests.factories import schools as f

pytestmark = pytest.mark.schools_db


def test_roster_import_2000_rows_under_30s(client, world, db):
    with db.cursor() as cur:
        cur.execute("UPDATE schools SET seat_limit = 5000 WHERE id = %s", (world.school_a["id"],))
    rows = ["name,grade,roll number,class,sign-in"] + [
        f"Student {i},{6 + i % 4},R-{i:05d},Perf {i % 40},pin" for i in range(2000)]
    t0 = time.perf_counter()
    r = client.post(f"/api/v1/schools/{world.school_a['id']}/students/import?dry_run=false",
                    json={"csv": "\n".join(rows)}, headers=world.headers("SA"))
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["create"] == 2000 and r.json()["summary"]["created_classes"] == 40
    assert f.fetch(db, "SELECT count(*) AS n FROM school_students WHERE school_id = %s",
                   (world.school_a["id"],))[0]["n"] == 2000 + 3
    print(f"PERF-03 roster import 2000 rows: {elapsed:.1f}s")
    assert elapsed < 30
