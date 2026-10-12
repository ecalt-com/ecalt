# Schools & Teacher-Built Courses — Testing Model

Plan: `README.md` · Tickets: `TRACKER.md` · Frontend contract: `frontend-changes.md`

This feature puts **children's data from many schools** into one database and shows **AI-written content to children**. The testing model is built around that:

1. **Invariants first.** A short list of things that must never happen (§1). Every one has a dedicated suite that runs on every change.
2. **Run SQL against a real database for anything that enforces tenancy.** Today's tests mock `get_db`, so the `WHERE school_id = …` clauses that prevent cross-school leaks would never actually execute. Isolation and authorization suites therefore run on a disposable Postgres (§3, L3).
3. **The authorization matrix is a spec written as data** (§4). It is written before the endpoints, and a coverage test fails when a route has no row.
4. **AI behaviour is tested twice:** deterministically with a fake provider (does the pipeline do the right thing with any output?) and statistically with evals on a document corpus (is the output good enough?).
5. **Tests never touch production.** `backend/.env` points at the prod Supabase. Every layer has a guard (§8).

---

## 1. Invariants

| ID | Invariant | Primary suites | Layer |
|---|---|---|---|
| I1 | No member of school A can read or change anything that belongs to school B | ISO-*, AUTHZ-* | L3 |
| I2 | A school student can only reach routes in `STUDENT_ALLOWED_ROUTES`; every other route returns 403 | SEC-01, SEC-02 | L2 |
| I3 | A student only sees school courses assigned to one of their **active** classes; non-school journeys are denied to students in v1 | INV-03, ISO-10..18 | L3 |
| I4 | Students never see content that a teacher hasn't published (drafts, unreviewed AI output, critic flags) | INV-04 | L3 |
| I5 | Nothing automatic overwrites `locked` step content (lazy regen, regenerate, feedback, warm-up, cache-miss generation) | INV-05 | L2 + L3 |
| I6 | School courses never appear in the marketplace, sitemap, suggestions, recommendations, learning context, public lists or forks | INV-06 | L3 |
| I7 | Student secrets can't be brute-forced (lockouts), and student sessions expire | SEC-03..07 | L2 |
| I8 | Uploaded files can't execute, escape the sandbox, or exhaust CPU or memory | DOC-*, SEC-10 | L1 + L4 |
| I9 | Document text can't change what the pipeline outputs beyond the schema; the result is always a draft for review | SEC-11, EV-INJ | L4 + L5 |
| I10 | Publishing a new version never loses progress on retained steps | INV-10, DBI-PROG-* | L3 |
| I11 | School-context AI usage is charged to the school pool; students never hit a personal free-trial limit | INV-11, UNIT-BUD-*, DBI-BUD-* | L1 + L3 |
| I12 | No email, WhatsApp, push or upsell ever targets a school student | INV-12 | L2 + L3 |
| I13 | Deleting a teacher's account doesn't delete school courses (a); deleting a student removes all their data incl. Firebase (b); terminating a school removes everything after the grace period (c) | INV-13a/b/c, DBI-DEL-* | L3 |

Each invariant suite lives in `tests/**/schools/test_invariants_*.py`. A failure in any of them blocks a merge, with no exceptions and no quarantine.

---

## 2. Test ID families

| Prefix | Meaning | Location |
|---|---|---|
| `INV-nn` | Invariant suite for I-nn | `tests/integration/schools/test_invariants_*.py` (+ unit parts) |
| `AUTHZ-*` | Generated authorization matrix (§4) | `tests/integration/schools/test_authz_matrix.py` |
| `ISO-nn` | Tenant isolation / IDOR sweep | `tests/integration/schools/test_isolation.py` |
| `SEC-nn` | Security tests (§5) | `tests/api/schools/test_security_*.py` |
| `DOC-nn` | Document handling against the fixture corpus (§6) | `tests/services/schools/test_documents.py` |
| `AI-nn` | AI pipeline with the fake provider | `tests/services/schools/test_pipeline_*.py` |
| `EV-*` | Offline evals (§7) | `scripts/evaluate_school_course.py` |
| `UNIT-<AREA>-*` | Pure logic | `tests/unit/schools/` |
| `API-<AREA>-*` | Endpoint behaviour (validation, shapes, error codes) | `tests/api/schools/` |
| `DBI-<AREA>-*` | SQL correctness on real Postgres | `tests/integration/schools/` |
| `DB-nn` | Migration tests: DB-01 applies on the baseline, idempotent, RLS on every new table · DB-02 D11 CHECK · DB-03 composite FKs reject cross-school links · DB-04 one draft per course · DB-05 new CHECK values | `tests/integration/schools/test_migration_014.py` |
| `PERF-nn` | Load and performance | `backend/loadtests/` (locust) |
| `E2E-nn` | Browser smoke flows | `frontend/e2e/` (Playwright, D10) |
| `CONTRACT-nn` | Backend ↔ frontend API contract | `tests/api/schools/test_openapi_snapshot.py` |

---

## 3. Test layers

| Layer | What | Tooling | DB | Runs |
|---|---|---|---|---|
| **L1 Unit** | Pure logic: permission predicates, secret hashing/lockout maths, join-code generation, CSV parsing/validation, chunker, scanned/garbled detection, alignment scoring, budget arithmetic, struggling flags, CSV escaping | pytest | none (`get_db` patched) | every push |
| **L2 API** | Request validation, response shapes, error codes, dependency wiring, student allowlist, rate-limit keys | pytest + `TestClient`; identity via patched `_verify_firebase_token` (so the **real** dependency chain runs) | mocked | every push |
| **L3 DB integration** | Tenancy SQL, authz matrix, isolation sweep, publish transaction, version/progress rules, budget pool, deletion cascades, job queue (`SKIP LOCKED`), migration 014 | pytest marker `schools_db`; disposable Postgres; transaction-per-test rollback; factories | **local Postgres only** | every push (CI service container) |
| **L4 Pipeline** | Extraction subprocess, chunking, job handlers, outline/build/update orchestration with the **fake provider** (canned, malformed, slow, failing outputs) | pytest + `tests/fakes/fake_provider.py` + fixture corpus | L3 DB for job tests | every push |
| **L5 AI evals** | Output *quality* on a document corpus with real models | `scripts/evaluate_school_course.py` (pattern of `scripts/evaluate_quiz_alignment.py`), LLM judge + human sample | dev DB or none | on every prompt/model change; before G4/G6/G8; weekly during the pilot |
| **L6 Security** | Allowlist enumeration, IDOR sweep, upload fuzz, injection corpus, brute force, session expiry, CSV injection, log hygiene | pytest (L2/L3/L4) | mixed | every push; full sweep at G5 and G8 |
| **L7 E2E** | 7 critical browser flows (§7.3) | Playwright vs Railway dev + Vercel preview, seeded "ECALT Test School" | dev | nightly + before each gate |
| **L8 Performance** | Classroom burst, roster import, generation throughput, progress matrix | locust | dev | G5, G8 |
| **L9 Pilot / UAT** | Real school, real documents, acceptance criteria (§11) | checklist + feedback form | prod (pilot school only) | M5 onward |

### L3 harness (SC-004, as built)
```bash
cd backend
docker compose -f tests/db/docker-compose.yml up -d          # postgres:15-alpine on 127.0.0.1:54329, tmpfs
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54329/ecalt_test \
  DATABASE_URL=postgresql://x:y@127.0.0.1:1/none pytest -m schools_db
```
- Plain `postgres:15-alpine`; `tests/db/prelude.sql` creates the Supabase roles (`anon`, `authenticated`, `service_role`), the `extensions`/`auth` schemas and an `auth.uid()` stub. `tests/db/prepare_schema.py` turns a schema-only dump into `tests/db/schema_baseline.sql`, dropping Supabase-only extensions and the realtime publication. It **refuses any input containing INSERT/COPY**, so `supbase/data.sql` (a prod data dump) can't end up in the repo.
- `tests/schools/harness.py` builds the database from prelude + baseline + every migration after `BASELINE_MIGRATION` (12), and rebuilds only when one of those files changes (fingerprint stored as the comment on schema `public`). It refuses any URL whose host isn't local/CI or whose database isn't `ecalt_test`, and re-checks `current_database()`.
- The `db` fixture points the app's connection pool at `ecalt_test` **for one test** (other tests keep the dead URL), uses real commits, and truncates every table afterwards (~45 ms). Real commits mean nested `get_db()` calls, row locks and later `SKIP LOCKED` worker tests behave as in production; a rolled-back outer transaction would hide those.
- Without `TEST_DATABASE_URL` the `schools_db` tests skip, so plain `pytest` still runs anywhere.

### Identity in tests
`tests/schools/identity.py` patches `core.auth._decode_firebase_token` so that `Authorization: Bearer test:<uid>[:auth_time]` resolves to `<uid>` (extra claims such as a verified email via `identity.register(uid, email=…, email_verified=True)`). Every dependency — profile resolution, the student allowlist, the status check, school membership — then runs for real. Avoid `dependency_overrides` in school tests, because overriding skips exactly the layers under test.

### Factories (`tests/factories/schools.py`)
As built: `make_user`, `make_school(status=, seats=, budget_cents=, dpa=True)`, `make_staff(school, role)`, `make_student(school, grade=, status=)`, `make_class(school, teachers=[…])`, `enroll(cls, student, removed=)`, `make_course(school, creator, published=True, steps=n, locked=True)`, `assign(cls, course, status=, due_at=)`, `make_journey(owner)` (ordinary journey), `make_family_profile(parent)`, plus `step_ids` / `fetch` helpers. `make_document`, `make_progress` and student secrets arrive with M2/M3.

The standard **world** fixture (`tests/schools/fixtures.py`) builds two schools A and B with every persona from §4 plus classes A1/A2/B1, published course C1 (assigned to A1), a draft course, school B's course CB and an ordinary journey N1, so any test can say "as `T2`, call X on A's class". `world.headers(persona)` returns the request headers.

---

## 4. Authorization matrix

### Personas
| Code | Who |
|---|---|
| ANON | No token |
| OUT | Signed-in adult with no school membership |
| PRF | Family child profile (parent token + `X-Profile-Id`) |
| SA | Owner/admin of school A |
| T | Teacher in school A, lead of class A1, creator of course C1 |
| T2 | Teacher in school A, not on class A1, not creator of C1 |
| S | Student of school A, enrolled in A1 (C1 assigned to A1) |
| S2 | Student of school A, enrolled only in A2 (C1 not assigned) |
| SX | Student of school A whose enrollment in A1 was removed |
| XA | Admin of school B |
| XS | Student of school B |
| ADM | ECALT admin (no school membership) |

### Expected results (✅ allowed · 403 role/route denied · 404 hidden · ⚙ depends on a setting)

| Action (school A resource) | ANON | OUT | PRF | SA | T | T2 | S | S2 | SX | XA | XS | ADM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Read / update school settings | 401 | 404 | 403p | ✅/✅ | ✅/403 | ✅/403 | 403 | 403 | 403 | 404 | 403 | 404 |
| Invite / remove staff | 401 | 404 | 403p | ✅ | 403 | 403 | 403 | 403 | 403 | 404 | 403 | 404 |
| Create / import / delete students | 401 | 404 | 403p | ✅ | ⚙ D9 | ⚙ D9 | 403 | 403 | 403 | 404 | 403 | 404 |
| Reset a student's secret | 401 | 404 | 403p | ✅ | ✅ own class | 403 | 403 | 403 | 403 | 404 | 403 | 404 |
| Create class | 401 | 404 | 403p | ✅ | ✅ | ✅ | 403 | 403 | 403 | 404 | 403 | 404 |
| Update class A1 / enroll / rotate code | 401 | 404 | 403p | ✅ | ✅ | 403 | 403 | 403 | 403 | 404 | 403 | 404 |
| Upload / read documents | 401 | 404 | 403p | ✅ | ✅ | ✅ | 403 | 403 | 403 | 404 | 403 | 404 |
| Create course | 401 | 404 | 403p | ✅ | ✅ | ✅ | 403 | 403 | 403 | 404 | 403 | 404 |
| Edit / publish course C1 | 401 | 404 | 403p | ✅ | ✅ | 403 | 403 | 403 | 403 | 404 | 403 | 404 |
| View / duplicate C1 (staff view incl. draft) | 401 | 404 | 403p | ✅ | ✅ | ✅ | 403 | 403 | 403 | 404 | 403 | 404 |
| Assign C1 to A1 | 401 | 404 | 403p | ✅ | ✅ | 403 | 403 | 403 | 403 | 404 | 403 | 404 |
| Class A1 progress / student drill-down | 401 | 404 | 403p | ✅ | ✅ | 403 | 403 | 403 | 403 | 404 | 403 | 404 |
| Tutor transcripts of A1 students | 401 | 404 | 403p | ⚙ D4 | ⚙ D4 | 403 | 403 | 403 | 403 | 404 | 403 | 404 |
| Learner: `GET /journeys/C1`, step content, quiz, progress, tutor | 404 | 404 | 404 | ✅ (staff view) | ✅ | ✅ | ✅ (tutor ⚙) | 404 | 404 | 404 | 404 | 404 |
| Learner: a non-school journey | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 403 (D5) | 403 | 403 | ✅ | 403 | ✅ |
| `/explore`, `/spark`, `/chat/stream`, `/family/*`, `/subscriptions/checkout`, `/coupons`, `DELETE /users/me` | — | ✅ | per today | ✅ | ✅ | ✅ | 403 | 403 | 403 | ✅ | 403 | ✅ |
| `/admin/schools*` | 401 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | ✅ |

Notes:
- `403p` = 403 `parent_profile_required`: staff routes act as the signed-in account, so a family-profile header is rejected before any school lookup (it reveals nothing about the school).
- Staff routes also need the parent PIN unlock (`X-Parent-Unlock`) when the staff member's account has family profiles (they build on `get_parent_session`).
- Cross-tenant is always **404**, never 403 (no existence disclosure).
- A student calling a staff route gets **403** `school_student_not_allowed` from the allowlist, before any school lookup.
- An archived student and every student or staff member of a **suspended** school get 403 `school_access_suspended` on everything except `GET /users/me`.

### Implementation
- `tests/integration/schools/authz_matrix.py` holds `MATRIX: list[Case(method, template, kind, path, body, expect)]`. A `kind` (`member`, `school_admin`, `owner`, `account`, `public`, `ecalt_admin`) supplies the default outcome per persona and `expect` overrides single cells. Path parameters and bodies are built from the world fixture. The runner parametrizes over every (row × persona) pair (M1: 16 rows × 12 personas).
- **Coverage test (`AUTHZ-COV`):** every route in `app.routes` whose path starts with `/api/v1/schools`, `/api/v1/school-login`, `/api/v1/school-student` or `/api/v1/admin/schools` must appear in `MATRIX`. A new endpoint without a row fails CI.
- **IDOR sweep (`ISO-*`):** for every route with path parameters, call it as SA of school A with each parameter swapped for the matching school-B object (class, student, course, document, job, assignment, proposal, version). Expect 404 every time, and assert that no school-B row was modified (row hash before and after).
- **Journey-path sweep (`ISO-10..18`):** every learner endpoint that takes a `journey_id` (SC-107 list) is called with C1 by S2, SX, XS, OUT and PRF. Expect 404, and expect **no model call** (the fake provider's call count stays 0) and **no `step_content` write**.

---

## 5. Security tests

| ID | Test |
|---|---|
| SEC-01 | **Route enumeration:** every route in `app.routes` is classified as student-allowed or student-denied. Unclassified → fail. The allowed list equals `STUDENT_ALLOWED_ROUTES` exactly |
| SEC-02 | A student token calls every denied route (with plausible bodies) → 403 `school_student_not_allowed`, with no side effects |
| SEC-03 | 5 wrong secrets → `423 student_locked` for 15 min; a correct secret during the lock is still rejected; the counter resets on success |
| SEC-04 | A class-code failure flood throttles the code. The throttle keys on code + student, **not IP**: 40 students behind one IP can all sign in |
| SEC-05 | Unknown class code, unknown student and wrong secret return uniform error shapes; secrets compared in constant time; secret hashes never appear in any response |
| SEC-06 | Rotating a QR badge invalidates the old badge immediately |
| SEC-07 | A student token older than `SCHOOL_STUDENT_SESSION_HOURS` (`auth_time`) → 401 `school_session_expired`; staff tokens are unaffected |
| SEC-08 | Rate limits on school endpoints key on uid / class / school; this documents the proxy-IP behaviour found in SC-009 |
| SEC-09 | Signed upload URLs are scoped to `{school_id}/{document_id}/` and expire; completing a document from another school → 404 |
| SEC-10 | Upload validation: extension/magic mismatch, size lie (declared vs actual), `.docm`/macro-bearing `.docx`, `.doc`, executables renamed `.pdf` → `document_rejected` + reason |
| SEC-11 | Prompt-injection fixtures (DOC-12) → output is still schema-valid, contains no injected instructions, links or HTML, and stays a draft; fake-provider variant asserts the delimiter and data-labelling in the prompt |
| SEC-12 | CSV export escapes cells starting with `= + - @` and tab/CR; CSV import treats them as plain text |
| SEC-13 | Log hygiene: `caplog` over login, import and generation flows shows no secrets, PINs, badge tokens, student display names or document text |
| SEC-14 | Join codes: alphabet without look-alikes, length, uniqueness under 10k generations, rotation invalidates the old code |
| SEC-15 | Admin impersonation of a student is audited (existing `admin_impersonation_audit`) and can't call staff routes |

---

## 6. Fixtures: document corpus (SC-007)

Generated by `tests/fixtures/school_docs/build_fixtures.py` (python-docx; reportlab from `requirements-dev.txt` for PDFs). The generated files are committed so tests are deterministic. **Only self-written or openly licensed content (e.g. OpenStax, CC BY); no copyrighted textbooks in the repo.** The pilot school's real documents stay outside the repo and are used only by L5 evals.

| ID | Fixture | Expected |
|---|---|---|
| DOC-01 | Clean 5-page text PDF with headings | `ready`, chunks follow sections, page ranges correct |
| DOC-02 | DOCX with headings, lists, tables | `ready`, heading paths, tables as markdown |
| DOC-03 | Image-only (scanned) PDF | `needs_ocr` |
| DOC-04 | Hindi (Devanagari) PDF + DOCX | `ready` with readable text; a broken-font variant → `needs_ocr` |
| DOC-05 | 301-page PDF | rejected (`too_many_pages`) |
| DOC-06 | 26 MB file | rejected at `upload-url` (declared) and at `complete` (actual) |
| DOC-07 | Password-protected PDF | rejected (`encrypted`) |
| DOC-08 | Truncated / corrupt PDF | `failed` with error code; the worker survives |
| DOC-09 | Executable renamed `.pdf` | rejected (magic bytes) |
| DOC-10 | DOCX zip bomb | rejected before parsing |
| DOC-11 | DOCX with an XXE entity | entity not resolved; no file read |
| DOC-12 | Prompt-injection document ("ignore previous instructions…", fake system tags, links) | see SEC-11 |
| DOC-13 | `.docm` and legacy `.doc` | rejected with a "save as .docx/PDF" message |
| DOC-14 | Maths-heavy document (equations, symbols) | `ready`; symbols preserved |
| DOC-15 | Revision pair v1/v2 of one chapter: edited section, removed section, added section, reordered sections | drives UNIT-ALIGN, AI-16..18, EV-UPD |
| DOC-16 | PDF that makes the parser spin (deep nesting / huge object stream) | subprocess timeout → `failed`; the API stays responsive |
| DOC-17 | Teacher marks sheet with student names | `ready`; UI warns (heuristic flag) — later |

---

## 7. AI testing

### 7.1 Deterministic pipeline tests (L4, fake provider)
`fake_provider` returns canned responses per interaction type and records prompts, call counts and concurrency. Modes: `ok`, `malformed_json`, `missing_citations`, `bad_chunk_ids`, `timeout`, `exception`, `slow` (for concurrency and cancellation).

| ID | Test |
|---|---|
| AI-01 | The new interaction types exist in `DEFAULT_CONFIG` with code-default prompts |
| AI-02 | Every model those types use has a `COST_PER_TOKEN` entry |
| AI-03 | A DB `style_prompt` overrides the code default (same mechanism as other types) |
| AI-04 | Outline and step-content contracts parse the canned outputs into the expected models |
| AI-05 | Malformed outline → one retry → the job fails with a visible error; no partial draft |
| AI-06 | Citations to non-existent chunk ids are rejected and retried |
| AI-07 | Coverage validation: an uncited, unskipped top-level section fails validation |
| AI-08 | The estimate matches the token maths; an exhausted school budget blocks **before** any model call |
| AI-09 | Build concurrency never exceeds `SCHOOL_GENERATION_CONCURRENCY` |
| AI-10 | A step prompt contains only its cited chunks (plus outline/context), with delimiters and the untrusted-data label |
| AI-11 | Critic flags are stored on the draft and absent from every student-facing response |
| AI-12 | Quiz anchors are derived from source facts |
| AI-13 | One step fails → that step is marked failed and retryable, the other steps succeed, and the job reports partial success |
| AI-14 | Cancelling mid-build stops further model calls; completed steps are kept |
| AI-15 | Regenerating a teacher-edited step without `overwrite_teacher_edits` → 409; with it → replaced and `origin='ai'` |
| AI-16 | Update proposals never `modify` a teacher-origin step (suggestion only) |
| AI-17 | Proposals reference valid step ids and positions |
| AI-18 | Replace mode keeps step ids where titles match |
| AI-19 | Usage is recorded per call with `school_id`; `school_usage` increments |

### 7.2 Quality evals (L5, SC-411 / SC-607)
`scripts/evaluate_school_course.py --corpus <dir> --grade <n> [--judge-model …] --out report.json` runs the real pipeline on each document and scores it. The thresholds below are the **release gates** for G4 and G6. Review them after the SC-008 spike and record any change in the tracker change log.

| ID | Metric | Method | Threshold |
|---|---|---|---|
| EV-01 | Outline coverage | top-level sections cited by a step or skipped with a reason | ≥ 90 % |
| EV-02 | Faithfulness | LLM judge splits step bodies into atomic claims and checks each against the cited chunks | unsupported ≤ 2 % of claims; **0** contradictions |
| EV-03 | Citation validity | every step cites ≥ 1 chunk; the step's key terms overlap the cited text | 100 % / overlap ≥ 0.3 |
| EV-04 | Grade fit | readability estimate vs target grade (English); judge rubric for Hindi | ≤ target + 2 grades |
| EV-05 | Quiz answerability | reuse the `evaluate_quiz_alignment.py` approach on the published content | ≥ 85 % |
| EV-06 | Teacher rubric (human) | pilot teachers rate a 10 % sample of steps 1–5 (accuracy, clarity, level) | mean ≥ 4.0; no step ≤ 2 on accuracy |
| EV-07 | Latency / cost | per 100 pages: outline time, full build time, cost | outline < 90 s; build < 10 min; cost within the SC-008 budget |
| EV-INJ | Injection resistance | DOC-12 variants × 10 runs | 0 successes |
| EV-OCR | OCR quality (M3b) | character error rate on scanned fixtures | ≤ 3 % |
| EV-UPD-01 | Alignment | precision / recall of the step ↔ new-section mapping on DOC-15 + pilot pairs | ≥ 0.9 / ≥ 0.9 |
| EV-UPD-02 | Changed sections detected | | ≥ 90 % |
| EV-UPD-03 | Unchanged steps rewritten | | 0 |
| EV-UPD-04 | New sections → `add` proposals | | ≥ 90 % |

Every eval run writes a dated report to `backend/plans/school-courses/evals/<date>-<change>.md`: model and prompt versions, scores, diff against the last run. A prompt or model change can't ship if a gated metric regresses.

### 7.3 E2E smoke (L7, D10)
| ID | Flow |
|---|---|
| E2E-01 | ECALT admin creates a school → owner accepts the invite → accepts the DPA → invites a teacher, who accepts |
| E2E-02 | Teacher imports a roster CSV (dry run → commit) → creates a class → opens printable login cards |
| E2E-03 | Student: class code → name → picture password → home → sign out; the 5-failure lockout message appears |
| E2E-04 | Upload a PDF and a DOCX → both reach `ready`; a `.doc` upload shows the conversion message |
| E2E-05 | Create a course from the PDF → edit and approve the outline → build → edit a step → preview as student → publish |
| E2E-06 | Assign to class → student completes a step and a quiz → teacher sees progress |
| E2E-07 | Upload a revised document → review proposals → publish v2 → student keeps progress and sees the "updated" badge |

Runs against Railway dev + a Vercel preview with a seeded "ECALT Test School" (`scripts/seed_test_school.py`, dev only, refuses to run against prod). The AI provider is real on dev, so E2E checks flow, not wording.

---

## 8. Environments and safety rails

| Context | DB | Guard |
|---|---|---|
| Unit / API / security (L1, L2, most of L6) | none | `DATABASE_URL=postgresql://x:y@127.0.0.1:1/none` (existing rule); an autouse fixture fails any test that opens a real connection |
| DB integration (L3, L4) | local Postgres `ecalt_test` | conftest **refuses to run** unless the host is `127.0.0.1`, `localhost` or the CI service name **and** the database name is `ecalt_test` |
| Job worker | — | `SCHOOL_JOBS_WORKER_ENABLED=false` in every test except worker tests, which run their own in-process worker against `ecalt_test` |
| E2E (L7), load (L8) | Railway **dev** | seed script and locust config refuse prod hostnames |
| Evals (L5) | none / dev | real API keys; costs logged in the report |
| Pilot (L9) | prod | only the pilot school exists; `SCHOOLS_ENABLED` on, but nobody can self-create a school |

Settings read from `.env`, so every test that depends on a `SCHOOL_*` flag patches it explicitly (existing rule in `backend/.claude/CLAUDE.md`).

---

## 9. Release gates

| Gate | Before | Must pass |
|---|---|---|
| G0 | Starting M1 | CI running; L3 harness green on migration 014 draft (DB-01..05); spike report merged into README |
| G1 | Starting M2 | AUTHZ (staff rows) + AUTHZ-COV + ISO + INV-03/05/06/13a + SEC-01/02 green; no regression in the existing suite vs the 62-failure baseline |
| G2 | Real student data in any environment | SEC-03..07, SEC-13/14, INV-13b green; **legal sign-off (SC-002)** |
| G3 | Building on ingestion | DOC-01..16 all as expected; worker stale-lock + retry tests green |
| G4 | Teachers see AI drafts (dev) | AI-01..15 green; EV-01..05 + EV-INJ at threshold on the corpus; INV-04/05 green |
| G5 | **Pilot go-live** | everything above + E2E-01..06 green twice in a row; PERF-01..04 at target; security review pass 1 with no open High findings; INV-11/12 green; runbook drafted |
| G6 | Updates shipped to the pilot | AI-16..18, INV-10, EV-UPD-* at threshold; E2E-07 green |
| G7 | Analytics shipped | API-ANL, SEC-12, PERF-04 at 40 × 20 green; AUTHZ transcript rows match D4 |
| G8 | GA | full security sweep (SC-801), PERF-01..06, INV-13c offboarding verified on dev, legal copy live, pilot sign-off (§11) |

### Performance targets (L8)
| ID | Scenario | Target |
|---|---|---|
| PERF-01 | 40 student logins within 60 s from **one IP** | p95 < 1.5 s, 0 throttled |
| PERF-02 | 30 students reading cached step content at once | p95 < 500 ms |
| PERF-03 | Roster import of 2,000 rows | < 30 s, single transaction, all-or-nothing |
| PERF-04 | Class progress matrix, 40 students × 20 courses | < 1 s |
| PERF-05 | 100-page document, full build at concurrency 4 | < 10 min |
| PERF-06 | 10 schools queue builds at once | per-school concurrency respected; no school waits > 2 × its fair share |

---

## 10. Definition of Done (every ticket)

- [ ] The ticket's tests (Tests column in `TRACKER.md`) exist and pass. Bug fixes include a regression test.
- [ ] New `/schools*`, `/school-login*` or `/school-student*` route → row in `MATRIX` (AUTHZ-COV enforces it) **and** classified for students (SEC-01 enforces it).
- [ ] Every query on a school-owned table filters by `school_id` (reviewer checklist; ISO sweep backs it up).
- [ ] `DATABASE_URL=postgresql://x:y@127.0.0.1:1/none pytest` → failures ≤ the 62 baseline, **zero** under `tests/**/schools/`.
- [ ] `pytest -m schools_db` green on the local harness.
- [ ] Migration changes are idempotent, applied to the dev DB first, and listed in `TRACKER.md`.
- [ ] Prompt changes: code default **and** DB row updated; eval report attached (§7.2).
- [ ] API shape changes: OpenAPI snapshot updated (CONTRACT-01) **and** `frontend-changes.md` updated in the same change.
- [ ] Frontend changes: `npm run build` passes; manual check in light + dark, at 375 px and 1024 px (Chromebook); keyboard navigation; picture-password icons have accessible names.
- [ ] No PII, secrets or document text in logs; staff mutations write `school_audit_log`.
- [ ] `TRACKER.md` status, notes and change log updated.

---

## 11. Pilot acceptance (L9)

| Criterion | Target |
|---|---|
| A teacher turns one of their own chapters into a published course, including review | < 30 min |
| Generated steps accepted unchanged or with minor edits | ≥ 80 % |
| A class of students signed in and learning after the teacher says "start" | < 3 min |
| Cross-tenant or unpublished-content incidents | 0 |
| Student-facing errors (5xx, budget, login) per class session | < 1 % of requests |
| Teacher satisfaction (survey) | ≥ 4 / 5 |

**Bug severity during the pilot:**
- **S1** — data leak, a child sees inappropriate or unpublished content, or a class can't log in. Fix or disable within 4 h; stop the pilot if needed.
- **S2** — a core flow is broken (generation, publish, assignment). Fix within 1 day.
- **S3** — degraded experience with a workaround. Fix next release.
- **S4** — cosmetic.

---

## 12. CI pipeline (SC-005)

`.github/workflows/backend.yml`:
1. **unit-api**: Python 3.11, `pip install -r requirements.txt` (`requirements-dev.txt` arrives with the document fixtures), `DATABASE_URL=postgresql://x:y@127.0.0.1:1/none pytest -m "not integration and not schools_db"`. The 62 known failures are listed in `tests/known_failures.txt`; with `ECALT_KNOWN_FAILURES=xfail` (set only in CI) a conftest hook turns them into non-strict xfails, so the job is green today and any **new** failure turns it red. Local runs are unchanged. Shrinking that list is separate work.
2. **schools-db**: Postgres service container → load the baseline schema + migrations → `pytest -m schools_db`.
3. **contract**: CONTRACT-01 OpenAPI snapshot for the school routes.

`.github/workflows/frontend.yml`: `npm ci && npm run build` (+ `npm run lint` once eslint is installed). Playwright runs **nightly** against dev, not on every push.
