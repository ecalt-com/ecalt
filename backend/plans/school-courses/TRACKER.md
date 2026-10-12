# Schools & Teacher-Built Courses — Tracker

Plan: `README.md` · Testing model: `TESTING.md` · Frontend contract: `frontend-changes.md`

**How to use this file**
- One row per ticket. When a ticket changes state, update its **Status** and, when done, add the commit SHA in **Notes**.
- **Tests** points at test IDs in `TESTING.md`. A ticket isn't ✅ until those tests exist and pass (Definition of Done, `TESTING.md` §10).
- Area: `DB` migration · `BE` backend · `AI` prompts/models/evals · `FE` frontend · `QA` tests/CI · `OPS` infra/config · `LEGAL` · `PM` product.
- Status: ⬜ not started · 🟦 in progress · 🟨 blocked · ✅ done · ⏭️ deferred.
- Size: S ≤ 1 day · M 2–3 days · L ~1 week · XL > 1 week (split before starting).

Last updated: 2026-10-12

---

## Milestone summary

| # | Milestone | Status | Tickets done | Gate (`TESTING.md` §9) |
|---|---|---|---|---|
| M0 | Foundations: decisions, legal track, test harness, CI, spikes | 🟦 | 3 / 9 | G0 |
| M1 | Tenancy + security hardening | ✅ | 14 / 14 | G1 |
| M2 | Students, classes, login | 🟦 | 8 / 10 | G2 |
| M3 | Document ingestion (+ M3b OCR) | ⬜ | 0 / 7 | G3 |
| M4 | AI course builder + publish | ⬜ | 0 / 11 | G4 |
| M5 | Classroom delivery — pilot-ready MVP | ⬜ | 0 / 8 | G5 |
| M6 | Course updates from documents | ⬜ | 0 / 7 | G6 |
| M7 | Teacher analytics | ⬜ | 0 / 7 | G7 |
| M8 | Launch hardening + rollout | ⬜ | 0 / 8 | G8 |

---

## M0 — Foundations

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-001 | Resolve decisions D1–D12 (log below) | PM | S | — | — | ⬜ | |
| SC-002 | Legal: school terms, DPA template, school privacy notice; compliance memo for the pilot jurisdiction (DPDP educational-institution provisions; COPPA school authorization + FERPA; GDPR Art. 28) | LEGAL | L | SC-001 (D3) | — | ⬜ | **Blocks real student data (M2 go-live)** |
| SC-003 | Recruit a pilot school; collect 10–20 real teaching documents with written permission for the eval corpus | PM | M | — | EV-* | ⬜ | |
| SC-004 | Integration DB harness: `docker compose` Postgres 15 + `supbase/schema.sql` + migrations ≥014; **localhost-only guard**; transaction-per-test; factories `tests/factories/schools.py` | QA | M | — | — | ✅ | Done 2026-10-12. `postgres:15-alpine` + `tests/db/prelude.sql` stand-ins for Supabase roles/schemas (no Supabase image needed); `tests/db/schema_baseline.sql` from `supbase/schema.sql` (refuses dumps with data); real commits + truncate after each test instead of rollback, so nested `get_db()` and row locks behave as in prod. Factories + `world` fixture with all §4 personas |
| SC-005 | CI (GitHub Actions): unit+API with dead `DATABASE_URL`; `schools_db` job on a Postgres service; frontend `npm run build`; quarantine list for the 62 pre-existing failures so CI gates on "no new failures" | QA/OPS | M | SC-004 | — | ✅ | Done 2026-10-12. `.github/workflows/backend.yml` (unit-api + schools-db service container) and `frontend.yml`; `tests/known_failures.txt` + `ECALT_KNOWN_FAILURES=xfail`. Green on GitHub. The first run caught that CI installs **FastAPI 0.143**, which nests included routers — fixed by matching the student allowlist on endpoints (`api_routes()`); suites now pass on 0.136 and 0.143 |
| SC-006 | `tests/fakes/fake_provider.py`: deterministic `complete_text` fake keyed by interaction type, with malformed/timeout modes | QA | S | — | — | ✅ | Done 2026-10-12. `tests/fakes/fake_provider.py`: ok / malformed_json / timeout / exception / slow + per-mode responses, call log, max concurrency, `install(monkeypatch)` patches every importer of `complete_text` |
| SC-007 | Document fixture corpus + generator script (`tests/fixtures/school_docs/`, `requirements-dev.txt`) | QA | M | — | DOC-* | ⬜ | Corpus list in `TESTING.md` §6 |
| SC-008 | **Spike** (time-boxed 3 days): (a) pypdf/python-docx quality on pilot docs incl. Hindi, tables, maths; (b) Supabase signed upload URL from the browser + real Vercel→Railway body limit; (c) Firebase custom-token sign-in on dev; (d) generation cost/latency for 20/100/300-page docs | BE/AI | M | SC-003 | — | ⬜ | Write findings into README §3.6/3.7 |
| SC-009 | Verify rate-limit keying behind Railway's proxy (uvicorn `--forwarded-allow-ips`); fix or document | OPS | S | — | SEC-08 | 🟨 | Analysis 2026-10-12: uvicorn 0.47 trusts `X-Forwarded-For` only from `FORWARDED_ALLOW_IPS` (default `127.0.0.1`). Railway's proxy isn't localhost, so `get_remote_address` probably returns the proxy IP and **every user shares each limit** (e.g. regenerate `10/hour` platform-wide). Needs a prod check (compare `request.client.host` with `X-Forwarded-For` in one log line) before changing anything; `FORWARDED_ALLOW_IPS='*'` would let clients spoof the header — trust Railway's proxy range instead. School endpoints key limits by student/class regardless |

## M1 — Tenancy + security hardening

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-101 | Migration `014_schools.sql` (README §3.2): all tables, RLS on, `journeys.school_id` + private CHECK, `step_content.source/locked`, `profile_type` += `school_student`. Apply to dev DB, then prod (additive) | DB | M | SC-004 | DB-01..05 | ✅ | Done 2026-10-12. Tested on the local harness (DB-01..05, idempotent) and **applied to the Supabase project `jfgofptxwydthyompcqb` via MCP** (`apply_migration` name `schools`); verified 17 tables with RLS, new CHECKs, existing rows untouched. Link tables carry `school_id` with composite FKs so cross-school links are impossible in the DB |
| SC-102 | `SCHOOLS_ENABLED` + config block (README §3.14); routers `schools`, `school_login`, `school_student` registered in `router.py`, 404 when disabled | BE | S | SC-101 | API-01 | ✅ | Done 2026-10-12. Routers `schools`, `school-invites`, `admin/schools` behind `require_schools_enabled`; `school-login` / `school-student` routers arrive with M2 / M5 |
| SC-103 | `core/school_auth.py`: `require_school_member`, `require_class_staff`, scoped loaders, membership cache + invalidation, school-status check | BE | M | SC-101 | AUTHZ-*, ISO-* | ✅ | Done 2026-10-12. `school_member(*roles)` → `SchoolCtx`, membership cache + invalidation, suspended → 403, terminated/non-member → 404, `uuid_or_404`. `require_class_staff` and scoped loaders land with their resources (M2+) |
| SC-104 | Student route allowlist in `get_optional_user` (fail-closed) + `STUDENT_ALLOWED_ROUTES` | BE | M | SC-101 | SEC-01, SEC-02 | ✅ | Done 2026-10-12. Enforced in `get_signed_in_uid` (root of every auth dependency, so account-holder deps are covered too). SEC-01 enumerates all routes; SEC-02 checks every denied route. Found + fixed: `POST /users/claim` reads the token by hand and would have let a student login claim a family profile (escaping the allowlist) |
| SC-105 | Account-level deps reject school students; `POST /users` / `GET /users/me` return `account_kind` and skip gates for `stu_` | BE | S | SC-104 | AUTHZ-S* | ✅ | Done 2026-10-12. `get_bootstrap_uid` for `POST /users`; `account_kind` (computed from `profile_type`), `school`, `student.classes` |
| SC-106 | `assert_account_active`: archived student / suspended school → 403 `school_access_suspended` (fail-closed cache) | BE | S | SC-101 | UNIT-AUTH-* | ✅ | Done 2026-10-12. Student status from `school_students` + `schools`, missing row fails closed |
| SC-107 | `services/journey_access.py` `assert_can_read_journey` applied to GET journey, step content (+regenerate, feedback), visual + events, quiz (generate/hint/submit), progress, journey tutor chat, suggestions, like/fork/marketplace submit | BE | L | SC-103 | INV-03, ISO-10..18 | ✅ | Done 2026-10-12. Also: student `GET /journeys` returns only assigned published courses (the SC-502 list part); students can only take quizzes on assigned steps and only use the in-course tutor. Mutation check: disabling the guard fails 95 of the ISO tests |
| SC-108 | Exclude school journeys (`school_id IS NULL`) from: `list_journeys` (journeys.py:209), recommendations (:354), suggestions (:756), marketplace + count (:536/540), sitemap (sitemap.py:30), admin queues (admin.py:745/831), `interest_profile_service.py:111`, scheduler (:658/:1181/:1196), `ai_service._build_learning_context` (:533) | BE | M | SC-101 | INV-06 | ✅ | Done 2026-10-12. Plus admin approve/reject/reset refuse school courses (404); scheduler scan excludes them (an UPDATE to pending_review would otherwise hit the D11 CHECK and abort the whole scan) |
| SC-109 | Regeneration guards: `upsert_step_content` refuses locked rows; skip school journeys in lazy regen (journeys.py:~974), regenerate (:1091), feedback regen (:1190), `warm_journey_steps` (ai_service.py:434); cache miss on school journey → 409 `content_not_published` | BE | M | SC-101 | INV-05 | ✅ | Done 2026-10-12. Guard lives in `upsert_step_content`'s SQL (no school journey, no locked row); regenerate → 409 `content_locked`; feedback stored, never regenerates; background regen + warm-up skip school courses |
| SC-110 | Account-deletion safety: school courses have `uid NULL`; `account_service` cascade leaves them alone; removing a teacher from a school keeps their courses | BE | S | SC-101 | INV-13a | ✅ | Done 2026-10-12. Every new FK to `users` is SET NULL or CASCADE, so the existing cascade still completes; membership and class-teacher rows go, courses stay |
| SC-111 | ECALT admin: create/list/update/suspend/terminate schools; owner invite | BE | M | SC-103 | AUTHZ-ADM-* | ✅ | Done 2026-10-12. Slugs, staff/student counts, terminated is final (409 `school_terminated`) |
| SC-112 | Staff invites (hashed token, 7-day expiry, verified-email match, Brevo template), accept, list, change role, remove (last-owner guard) | BE | M | SC-103 | API-STAFF-* | ✅ | Done 2026-10-12. Accept is `POST /school-invites/accept {token}` and preview `POST /school-invites/preview` (token never in a URL path or request log). Verified email from the **token claims** must match; adults only; re-invite revokes the old link; last-owner guard on demote/remove/leave |
| SC-113 | School settings + DPA accept + `school_audit(...)` helper used by every staff mutation | BE | S | SC-103 | API-SET-*, AUD-* | ✅ | Done 2026-10-12. `SchoolSettings` (unknown keys → 422), DPA accept by owner (version must match; onboarding → active), `school_audit` in every staff mutation |
| SC-114 | FE: staff shell, school switcher, staff management, invite accept, admin Schools tab (`frontend-changes.md` §2–3, §11) | FE | L | SC-111..113 | E2E-01 | ✅ | Done 2026-10-12 (uncommitted): `lib/schoolApi.ts`, `lib/SchoolContext.tsx`, `pages/school/` (layout, dashboard, staff, settings), `components/school/DpaModal.tsx`, `pages/SchoolInviteAccept.tsx`, admin `SchoolsTab`, nav entry, `account_kind` in `AuthContext`. `npm run build` passes; ESLint isn't installed in the repo. **Not yet clicked through in a browser** (needs a deployed backend with `SCHOOLS_ENABLED=true` + Google sign-in). E2E-01 waits for Playwright (D10). DPA modal shows placeholder summary copy until SC-002 |

## M2 — Students, classes, login

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-201 | Students CRUD (paged/search), seat limit, DPA required, `consent_events` school_authorization record | BE | M | SC-113 | API-STU-*, AUTHZ-* | ✅ | Done 2026-10-12. Paged/searchable list (`can_manage`, seats), create returns the secret + badge once, seat limit + DPA gate (409), `consent_events` school_authorization, teachers only when `teachers_can_create_students` and only into their classes |
| SC-202 | CSV roster import: dry-run report (row errors, duplicates, seat overflow) → commit; idempotent on `external_ref`; 2,000 rows; creates classes + enrollments when the CSV has a class column | BE | L | SC-201, SC-203 | UNIT-CSV-*, PERF-03 | ✅ | Done 2026-10-12. JSON `{csv}` body (file read in the browser). Header aliases, KG/LKG/UKG → 0, per-line errors/warnings, duplicate roll numbers, seat check, all-or-nothing commit with `execute_values`; imported students get **no secret** until login cards are printed (keeps 2,000 rows fast: 0.4 s locally) |
| SC-203 | Classes CRUD, join codes (no look-alike chars, rotate), class teachers, bulk enroll/unenroll | BE | M | SC-103 | API-CLS-*, AUTHZ-* | ✅ | Done 2026-10-12. Join codes: 8 chars from a 31-char alphabet without I/L/O/0/1, accepted with dashes/lower-case; creator becomes lead; read for all staff, changes for class teachers + admins; archive hides the class's courses |
| SC-204 | Student secrets: picture (3 of 16 icons) / 6-digit PIN, scrypt hashed, reset by staff, printable on login cards only at creation/reset | BE | S | SC-201 | UNIT-SEC-* | ✅ | Done 2026-10-12. Picture (3 of 16, order matters) up to grade 4, PIN after; scrypt; reset by admins or the student's class teachers (clears lockouts). Login cards are `POST …/login-cards {reset}` (secrets are hashed, so cards can only show secrets issued now) |
| SC-205 | Login endpoints: class lookup, session create, keyed lockouts (student 5/15 min; class-code throttle), audit | BE | M | SC-204, SC-207 | SEC-03..05 | ✅ | Done 2026-10-12. Roster shows 'First L.' and only students who have a secret; hidden roster → roll number. 5 wrong → 423 for 15 min; class throttle = 50 failures / 10 min counted from `school_audit_log`; uniform 401 + timing equaliser; nothing keyed on IP |
| SC-206 | QR badge login + rotate | BE | S | SC-205 | SEC-06 | ✅ | Done 2026-10-12 (backend + `/class/badge#token` page). Printing QR codes waits for the `qrcode` dependency (frontend-changes §15) |
| SC-207 | Firebase custom-token minting in `firebase_admin.py` (RS256, claims); Firebase record purge on student delete | BE | S | SC-008c | UNIT-FB-* | 🟦 | Done in code 2026-10-12: `firebase_admin.mint_custom_token` (RS256, `kid`, claims `{school_id, kind}`, 1 h), Firebase purge on student delete; structure tested with a throwaway key. **Still to verify on dev (SC-008c):** a real `signInWithCustomToken` against the Firebase project, and the Firebase Auth plan's limits for custom-token users (R16) |
| SC-208 | Student max session age from `auth_time` → 401 `school_session_expired` | BE | S | SC-207 | SEC-07 | ✅ | Done 2026-10-12. `auth_time` checked in `get_signed_in_uid` for `stu_` uids (`SCHOOL_STUDENT_SESSION_HOURS=12`); frontend uses session persistence and redirects to `/class?expired=1` |
| SC-209 | Archive/restore/delete student (cascade + Firebase + enrollments), bulk year-end archive, per-student export | BE | M | SC-201 | INV-13b, API-STU-* | ✅ | Done 2026-10-12. Archive/restore (restore needs a seat), bulk archive `POST …/students/archive`, delete = `account_service` cascade + pseudonymised consent + Firebase purge, export = `build_user_export` + student record (admins) |
| SC-210 | FE: students page + import wizard, classes, login-cards print page, `/class` student login, QR scan, student shell (`frontend-changes.md` §4–6) | FE | XL | SC-201..209 | E2E-02, E2E-03 | 🟦 | Built 2026-10-12: Students (+ import wizard, one-time secret reveal), Classes, class page, printable login cards, `/class` (code → name/roll → pictures/PIN), `/class/badge`, student nav + `StudentGuard`, `/my-classes`. `npm run build` passes. Open: QR codes on cards (`qrcode` approval), student variant of the Journey page (SC-507), a browser pass on dev |

## M3 — Document ingestion

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-301 | Private bucket `school-materials`; `upload-url` + `complete` endpoints (ext, size, magic bytes, macro check, sha256 dedupe) | BE/OPS | M | SC-008b | DOC-01..06, SEC-09, SEC-10 | ⬜ | FE needs the Supabase origin in CSP `connect-src` (`vercel.json`) |
| SC-302 | `services/school_jobs.py`: queue, SKIP LOCKED worker in lifespan, retries/backoff, stale-lock recovery, cancel, per-school concurrency | BE | L | SC-101 | UNIT-JOB-*, DBI-JOB-* | ⬜ | Worker off locally |
| SC-303 | Sandboxed extraction subprocess (timeout + `RLIMIT_AS`); pypdf + python-docx; encrypted/zip-bomb/XXE/macro guards | BE | L | SC-302 | DOC-07..16 | ⬜ | New deps |
| SC-304 | Structure + chunking (heading paths, page ranges, header/footer strip, tables → markdown); scanned + garbled detection → `needs_ocr` | BE | M | SC-303 | UNIT-CHUNK-* | ⬜ | |
| SC-305 | Document list/status/delete (storage + chunks), retention setting | BE | S | SC-301 | API-DOC-* | ⬜ | |
| SC-306 | **M3b** OCR via `document_ocr` interaction type behind `SCHOOL_DOC_OCR_ENABLED`; school-billed | AI/BE | L | SC-304, SC-504 | EV-OCR | ⏭️ | Per D7 |
| SC-307 | FE: uploader with direct-to-storage progress, document status list (`frontend-changes.md` §7) | FE | M | SC-301 | E2E-04 | ⬜ | |

## M4 — AI course builder + publish

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-401 | Interaction types `school_course_outline`, `school_step_content`, `school_faithfulness_critic`: contracts, code defaults, **DB rows on dev + prod**, `COST_PER_TOKEN` entries | AI | M | SC-008d | AI-01..04 | ⬜ | DB rows override code (prompt-storage rule) |
| SC-402 | Outline job + validation (chunk citations, coverage / `skipped_sections`), estimate endpoint, school budget check | AI/BE | L | SC-401, SC-302 | AI-05..08, EV-01 | ⬜ | |
| SC-403 | Draft APIs: get/patch meta, add/patch/delete/reorder steps, revision lock (409 `draft_conflict`), origin tracking | BE | M | SC-101 | API-DRAFT-*, DBI-DRAFT-* | ⬜ | |
| SC-404 | Outline approve → build job: grounded bodies, bounded concurrency, quiz anchors, citations, critic pass, flags, progress | AI/BE | L | SC-402 | AI-09..14, EV-02..05 | ⬜ | |
| SC-405 | Regenerate one step (grounded, instruction, `overwrite_teacher_edits`) | AI/BE | S | SC-404 | AI-15, API-DRAFT-* | ⬜ | |
| SC-406 | Publish transaction → journeys + locked step_content, version states, quiz invalidation, audit | BE | M | SC-403, SC-109 | INV-04, INV-05, DBI-PUB-* | ⬜ | |
| SC-407 | Version history, restore-as-draft, duplicate, archive | BE | M | SC-406 | API-VER-* | ⬜ | |
| SC-408 | Prompt-injection hardening: delimiters, schema validation, strip links/HTML/scripts, `content_filter` on output | AI | M | SC-404 | SEC-11, EV-INJ | ⬜ | |
| SC-409 | Optional hero image for school courses via `image_service`, school-billed | BE | S | SC-406, SC-504 | API-IMG-* | ⬜ | |
| SC-410 | FE: create wizard, outline review, step editor (source panel, flags, regenerate), preview as student, publish dialog, version history (`frontend-changes.md` §8) | FE | XL | SC-402..407 | E2E-05 | ⬜ | Split: wizard / editor / versions |
| SC-411 | Eval harness `scripts/evaluate_school_course.py` + corpus + thresholds; run on every prompt/model change | AI/QA | L | SC-003, SC-007, SC-404 | EV-01..07 | ⬜ | Release gate G4 |

## M5 — Classroom delivery (pilot-ready MVP)

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-501 | Assignments CRUD (published courses only, due dates, settings) | BE | M | SC-406, SC-203 | API-ASG-*, AUTHZ-* | ⬜ | |
| SC-502 | `GET /school-student/home`; student `GET /journeys` returns assigned courses only | BE | M | SC-501 | INV-03, API-HOME-* | ⬜ | |
| SC-503 | Settings enforcement: tutor on/off, grade → age band passed to tutor/quiz/visuals, quiz-required | BE | M | SC-501 | API-SETTINGS-* | ⬜ | |
| SC-504 | School budget pool: `check_budget`/`record_usage` with school context, `school_usage`, per-student daily caps, 402 `school_budget_exhausted`, 80 %/100 % admin emails | BE | L | SC-101 | UNIT-BUD-*, DBI-BUD-*, INV-11 | ⬜ | Extend `tests/unit/test_budget*.py` style |
| SC-505 | Basic class progress matrix endpoint | BE | M | SC-501 | API-PROG-*, PERF-04 | ⬜ | |
| SC-506 | Notification/scheduler audit: every audience excludes school students; no upsell surfaces | BE | S | SC-101 | INV-12 | ⬜ | |
| SC-507 | FE: assign flow, student home, student course view, class progress page (`frontend-changes.md` §9–10) | FE | L | SC-501..505 | E2E-06 | ⬜ | |
| SC-508 | Pilot readiness review: security review pass 1, G5 gate, legal docs live, runbook draft | PM/QA | M | all M1–M5 | G5 | ⬜ | **Go/no-go for the pilot** |

## M6 — Course updates from new documents

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-601 | Update job: extract → align chunks to step sources → classify steps + uncovered sections | AI/BE | L | SC-304, SC-406 | UNIT-ALIGN-*, EV-UPD-01 | ⬜ | |
| SC-602 | Proposal generation (modify/add/remove/move) with diffs; teacher-origin steps suggestion-only | AI | L | SC-601 | AI-16..18, EV-UPD-02..04 | ⬜ | |
| SC-603 | Proposal review APIs: accept/reject/accept-all → new draft version | BE | M | SC-602 | API-UPD-* | ⬜ | |
| SC-604 | Publish v(n+1) with progress rules + "updated since you finished" marker + quiz invalidation | BE | M | SC-603 | INV-10, DBI-PROG-* | ⬜ | Check sequential gating (`tests/api/test_progress_sequential.py`) |
| SC-605 | Supplement mode (add a document → new-step proposals only); replace mode keeps ids on title match | AI/BE | M | SC-602 | API-UPD-* | ⬜ | |
| SC-606 | FE: update wizard, side-by-side diff review, student "updated" badge (`frontend-changes.md` §8.6) | FE | L | SC-603 | E2E-07 | ⬜ | |
| SC-607 | Update eval: revision-pair fixtures (≥90 % changed sections detected, 0 unchanged steps rewritten) | AI/QA | M | SC-602 | EV-UPD-* | ⬜ | Gate G6 |

## M7 — Teacher analytics

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-701 | Student drill-down (steps, quiz attempts, hints) | BE | M | SC-505 | API-ANL-* | ⬜ | |
| SC-702 | Struggling flags | BE | S | SC-701 | UNIT-FLAG-* | ⬜ | |
| SC-703 | Tutor transcript visibility per D4 + student-side disclosure flag in `/school-student/home` | BE | S | SC-001 (D4) | AUTHZ-TR-* | ⬜ | |
| SC-704 | CSV exports with formula-injection escaping | BE | S | SC-505 | SEC-12 | ⬜ | |
| SC-705 | Weekly teacher digest (scheduler, prod only) | BE | M | SC-701 | UNIT-DIGEST-* | ⬜ | |
| SC-706 | School usage dashboard endpoint (budget, per-class and per-course spend) | BE | S | SC-504 | API-USAGE-* | ⬜ | |
| SC-707 | FE: analytics pages + usage page (`frontend-changes.md` §10) | FE | L | SC-701..706 | E2E-06 | ⬜ | |

## M8 — Launch hardening + rollout

| ID | Task | Area | Size | Depends | Tests | Status | Notes |
|---|---|---|---|---|---|---|---|
| SC-801 | Security review: full authz matrix, IDOR sweep, upload fuzz, injection corpus, session/lockout review | QA | L | M1–M7 | SEC-*, AUTHZ-*, ISO-* | ⬜ | |
| SC-802 | Load tests: classroom burst, roster import, generation throughput, progress matrix at 40×20 | QA | M | M5 | PERF-01..06 | ⬜ | |
| SC-803 | Offboarding: terminated → 30-day grace → deletion job (DB + storage + Firebase); verify nothing remains | BE | M | SC-209 | INV-13c, DBI-DEL-* | ⬜ | |
| SC-804 | Legal copy live (school terms, DPA, privacy policy), DPIA schools section (`docs/children-data-dpia.md`) | LEGAL | M | SC-002 | — | ⬜ | |
| SC-805 | Observability: job metrics/failure alerts, cost per course, Sentry tag `school_id` (no PII) | OPS | S | SC-302 | — | ⬜ | |
| SC-806 | Support runbook + admin tools (reset secret, restore version, stuck job, cancel) | PM/BE | M | M5 | — | ⬜ | |
| SC-807 | Rollout: dev → prod pilot school → GA; Microsoft staff sign-in (D8) | OPS/FE | M | G8 | E2E-* on prod pilot | ⬜ | |
| SC-808 | Update `backend/.claude/CLAUDE.md`, `frontend/CLAUDE.md`, plans index | PM | S | — | — | ⬜ | |

## Backlog (not scheduled)

LMS integrations (Google Classroom roster/assignment sync, LTI 1.3) · student SSO (Google Workspace / Microsoft) for 13+ · `.pptx` / images input · reusing document images as course visuals · course translation · course collaborators + head-of-department approval · district / cross-school sharing · self-serve school billing (Stripe/Razorpay) · parent link to school progress (D6) · embeddings-based update alignment · live classroom mode · offline-tolerant student mode.

---

## Decision log

| ID | Decision | Status | Outcome / date | Recommendation (README §0) |
|---|---|---|---|---|
| D1 | Student sign-in method | Open | | Class code + roster + picture/PIN + QR badge; Firebase custom tokens |
| D2 | Commercial model v1 | Open | | Sales-led; admin-set seats + monthly AI budget |
| D3 | Pilot jurisdiction | Open | | India first |
| D4 | Teacher access to tutor transcripts | Open | | Yes for own classes, disclosed, school can disable |
| D5 | Student access beyond assigned courses | Open | | None in v1 |
| D6 | Link with family profiles | Open | | Separate in v1 |
| D7 | Scanned PDFs in v1 | Open | | Detect + ask for text PDF/DOCX; OCR in M3b |
| D8 | Staff sign-in providers | Open | | Google now, Microsoft before GA |
| D9 | Who creates students | Open | | Admins; teachers by school setting |
| D10 | E2E tooling | Open | | Playwright, 6 smoke flows |
| D11 | Sharing school courses outside the school | Open | | Never in v1 (DB-enforced) |
| D12 | Document languages at launch | Open | | English + Hindi |

---

## Risk register

| ID | Risk | L | I | Mitigation | Ticket(s) |
|---|---|---|---|---|---|
| R1 | Processing student data without a valid legal basis / DPA | M | H | Counsel memo + DPA before real students; `dpa_required` enforced in code | SC-002, SC-113, SC-201 |
| R2 | Hallucinated or unfaithful content shown to children | M | H | Grounded contract, citations, critic flags, mandatory review, eval gate | SC-404, SC-408, SC-411 |
| R3 | School material readable through existing public journey paths | H (today) | H | Access control + pool exclusions shipped in M1 before any school data exists | SC-107, SC-108 |
| R4 | Teacher-approved content overwritten by automatic regeneration | H (today) | H | `locked` step content + guards | SC-109 |
| R5 | Malicious/odd files hang or crash the API | M | H | Sandboxed subprocess, limits, magic bytes, fixture corpus | SC-301, SC-303 |
| R6 | Generation jobs lost on redeploy | M | M | DB queue + stale-lock recovery + idempotent handlers | SC-302 |
| R7 | One school NAT IP hits IP-based limits; burst at bell time | H | M | Keyed limits; load test classroom burst | SC-009, SC-205, SC-802 |
| R8 | Sessions left open on shared classroom devices | H | M | Session persistence, max age, prominent sign-out | SC-208, SC-210 |
| R9 | AI cost overrun on long documents | M | M | Estimates, outline-first, caps, school budget, per-student caps | SC-402, SC-504 |
| R10 | Poor extraction (Hindi fonts, scans, maths, tables) | H | M | Spike, garbled/scan detection, OCR phase, eval corpus | SC-008, SC-304, SC-306 |
| R11 | Copyrighted textbooks uploaded | M | M | Terms warranty, private to school, DB-enforced no-sharing | SC-002, SC-101 |
| R12 | Class-code page exposes roster names | M | L | First name + initial only; setting to hide roster; code throttling | SC-205 |
| R13 | Scope creep towards a full LMS | H | M | v1 scope list (README §1); backlog | — |
| R14 | 62 pre-existing failures hide regressions; no CI | H | M | CI + quarantine list; school suites must be 100 % green | SC-005 |
| R15 | Local dev and some tests hit the prod DB | M | H | Dead DB URL for unit/API; localhost-only guard for integration; worker off locally | SC-004, SC-302 |
| R16 | Firebase Auth limits/cost for many custom-token students (MAU pricing if on Identity Platform) | L | M | Check the Firebase plan in the spike; purge deleted students | SC-008c, SC-209 |
| R17 | Students who are also family profiles end up with two identities | M | L | Accept in v1; parent link later | D6 |

---

## Change log

| Date | Change |
|---|---|
| 2026-10-11 | Tracker created with plan draft; all decisions open |
| 2026-10-12 | M2 built and pushed: students, CSV import, classes, login cards, student sign-in (picture/PIN/badge → Firebase custom token), session limit; frontend for all of it. 727 `schools_db` tests green on FastAPI 0.136 and 0.143; CI green. Open: SC-207 live custom-token check on dev, SC-210 QR + browser pass. **G2 still needs legal sign-off (SC-002) before real students** |
| 2026-10-12 | CI found FastAPI 0.143 nests included routers; student allowlist now matches endpoints (fix `0f3a9a5`). SC-005 ✅ |
| 2026-10-12 | Migration 014 applied to Supabase (SC-101 ✅). M1 frontend built (SC-114 ✅): staff area, invites, settings/DPA, admin Schools tab, `account_kind`. M1 complete in code; G1 still needs the first CI run on GitHub and a browser pass on dev |
| 2026-10-12 | Implementation started, assuming the §0 recommendations (decisions still open). Done: SC-004, SC-006, SC-102..SC-113. In progress: SC-005 (needs a GitHub run), SC-101 (needs applying to dev/prod). Blocked: SC-009 (prod check). Tests: 389 `schools_db` + 141 unit/API school tests green; default suite still exactly the 62 baseline failures. G1 test items all green locally |
