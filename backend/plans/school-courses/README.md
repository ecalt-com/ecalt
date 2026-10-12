# Schools & Teacher-Built Courses Plan

**Goal:** Schools use ECALT to teach their own curriculum. A school gets a tenant; its admins and teachers create **student accounts** and **classes**, upload **PDF or Word documents** and turn them into ECALT courses with AI help. Teachers review and edit every course before students see it, assign courses to classes, update courses when the source material changes, and track each student's progress.

**Status:** Drafted 2026-10-11. Implementation started 2026-10-12 (M0 test harness/CI, M1 backend: tenancy, staff, student allowlist, journey access, leak and regeneration fixes) — see `TRACKER.md`. Decisions in §0 are still open; the code assumes the recommendations.

**Companion docs (this folder):**
| File | Purpose |
|---|---|
| `TRACKER.md` | Milestones, tickets (`SC-xxx`), status, dependencies, decision log, risk register |
| `TESTING.md` | Testing model: invariants, test layers, authorization matrix, fixtures, AI evals, CI, release gates |
| `frontend-changes.md` | Frontend contract: routes, screens, auth changes, error codes (frontend is specified here, not built in the backend phases) |

---

## 0. Decisions needed

Each decision has a recommended answer. The plan assumes the recommendation until the decision is made. Record the outcome in `TRACKER.md` → Decision log.

| ID | Question | Recommendation | Blocks |
|---|---|---|---|
| D1 | How do students sign in? | **Class code → pick your name → picture password (young) or 6-digit PIN (older)**, plus a printable **QR badge** per student. No student email or password. Students get Firebase **custom tokens**, so the existing auth stack works unchanged. Google Workspace / Microsoft SSO for 13+ comes later. | M2 |
| D2 | Commercial model for v1 | **Sales-led.** An ECALT admin creates the school and sets a seat limit and a monthly AI budget. Invoicing happens outside the app. Self-serve school checkout comes later. | M1, M5 |
| D3 | Pilot jurisdiction | **India first** (default geo `IN`, Razorpay), using the DPDP school framework. US (COPPA/FERPA) and EU (GDPR) after counsel review. | M0 legal |
| D4 | Can teachers read students' in-course tutor chats? | **Yes, for their own classes**, for safeguarding. Students see a notice saying so. Schools can turn it off. | M7 |
| D5 | What can students reach beyond assigned courses (open explore, spark, general chat)? | **Nothing in v1.** Students see only assigned courses plus the in-course tutor. A per-school setting can open more later. | M1 |
| D6 | How do school accounts relate to family profiles? | **Keep them separate in v1.** Later, a parent can link with a code to see school progress read-only. | — |
| D7 | Scanned (image-only) PDFs in v1? | **Detect them and ask for a text PDF or Word file.** OCR through a vision model ships behind a flag in M3b. | M3 |
| D8 | Staff sign-in providers | **Google** (works today). Add **Microsoft** (Firebase `microsoft.com` provider) before GA, because many schools use Microsoft 365. | M8 |
| D9 | Who creates student accounts? | **School admins.** A school setting lets teachers do it too. | M2 |
| D10 | End-to-end test tooling | **Add Playwright** to `frontend/`, limited to 6 smoke flows (see `TESTING.md` §7). The fallback is a manual QA checklist. | M5 gate |
| D11 | Can school courses be shared or published outside the school? | **Never in v1.** The database enforces this (§3.2). | — |
| D12 | Document languages at launch | **English + Hindi.** Other Indian languages after the extraction spike (SC-008) proves quality. | M3 |

---

## 1. Scope

**In v1**
- School tenants, staff roles (owner / admin / teacher), staff invites.
- Student accounts with no email, CSV roster import, classes, enrollments, class-code / picture / PIN / QR-badge login.
- PDF (text) and DOCX upload → extraction → AI **outline** (teacher approves) → AI **step content grounded in the document** → teacher edits → **publish**.
- Course versioning. **Updating a course from a revised or extra document** produces a reviewable change set.
- Assign courses to classes with due dates. Students get a home screen. The in-course tutor is on or off per class.
- School-pooled AI budget. Class progress views, per-student drill-down, CSV export.
- Compliance: DPA acceptance, school-authorization consent record, audit log, archive/delete/export, school offboarding.

**Out of v1 (backlog in `TRACKER.md`)**
LMS integrations (Google Classroom, LTI), gradebook sync, SSO for students, `.pptx` / `.doc` / images input, using images extracted from documents as course visuals, auto-translating courses, sharing within a district or between schools, self-serve school billing, parent link, live classroom mode.

---

## 2. Current state (audited 2026-10-11)

### What we reuse
- **A course *is* a journey.** `journeys` (steps as JSONB, `models/schemas.py:39`) and `step_content` (per-step lesson body + `quiz_anchors`, cached per `(journey_id, step_id)`) already drive the learner UI (`StepNode`), progress (`user_progress`), quizzes (`quiz_service` reads step content + anchors), the journey tutor, visuals and hero images. Students taking a school course therefore get the full learning loop without a new player.
- **Identity:** `users.uid` is a text PK and every learner table is keyed by it. A family profile is a `users` row without a login (`profile_type='profile'`, `prof_` uid). School students follow the same pattern (`profile_type='school_student'`, `stu_` uid).
- **Auth:** Firebase ID token → `core/auth.py` dependency chain (`get_optional_user:171` → `get_required_user` → `get_active_user`). `firebase_admin.py` already signs RS256 JWTs with the service account in `FIREBASE_SERVICE_ACCOUNT_JSON`. Minting **Firebase custom tokens** needs no new dependency.
- **Hashing / lockout:** `profile_service.hash_pin` (scrypt + salt) and the parent-PIN lockout pattern.
- **Storage:** `image_service` writes to Supabase Storage through `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.
- **AI plumbing:** `provider_service` interaction types (`complete_text`, DB-overridable prompts, cost table). `ai_service.generate_step_content` already builds context (outline, position, covered facts, seed facts, critic).
- **Compliance:** append-only `consent_events` (free-text `method`, so `school_authorization` needs no schema change), `account_service` deletion/export cascade, `content_filter`.
- **Budget:** `subscription_service.check_budget` / `record_usage`, which already pools family budgets.

### Gaps and hazards found in the audit (each one is fixed in M1)
1. **Any journey is readable by id.** `GET /journeys/{id}` (`journeys.py:724`) and step-content, quiz and progress endpoints never check access. School material would be readable by anyone holding the URL.
2. **School courses would leak into public pools:** the sitemap (`sitemap.py:30`, **public**, lists every non-curated journey), recommendations (`journeys.py:354`, `uid != me OR uid IS NULL`), suggestions (`journeys.py:756`, `SELECT * FROM journeys`), `interest_profile_service.py:111`, scheduler queries (`scheduler.py:658/1181/1196`) and admin marketplace queues (`admin.py:745/831`).
3. **Automatic regeneration would overwrite teacher-approved content:** prompt-version lazy regen (`journeys.py:~974`), the regenerate endpoint (`:1091`), feedback-triggered regen (`:1190`), `warm_journey_steps` (`ai_service.py:434`), and generation on a cache miss (`:986+`). `upsert_step_content(..., overwrite=True)` has no lock concept.
4. **Deleting a teacher's account would delete school courses**, because `account_service.py:38/184-196` deletes journeys `WHERE uid = <user>`.
5. **Budgets are per user or per family.** There is no organisation pool, so students would hit their own free-trial limit (`check_budget`, `subscription_service.py:139`).
6. **Rate limits key on remote IP** (`core/limiter.py`). Uvicorn runs without `--forwarded-allow-ips` (`Dockerfile`), so behind Railway's proxy every client probably shares one bucket. A classroom behind one school NAT would share one bucket anyway. School endpoints must key limits by student, class or school. *SC-009 (2026-10-12):* uvicorn 0.47 trusts `X-Forwarded-For` only from `FORWARDED_ALLOW_IPS` (default `127.0.0.1`), so unless Railway sets it, every user shares each limit. Confirm in prod before changing; `'*'` would let clients spoof the header.
7. **Long jobs have no durable runner.** `BackgroundTasks` die with the process. The APScheduler only runs in prod (`SCHEDULER_ENABLED`), so it can't host jobs that must also run on dev.
8. **There is no PDF/DOCX parsing** in `requirements.txt`.
9. **Test infrastructure:** unit/API tests mock `get_db`, so SQL is never executed. There is no CI. 62 tests already fail on `feature/dev`. `backend/.env` points at **prod**. The frontend has no test suite. `supbase/schema.sql` (a schema-only dump, untracked) can seed a disposable local Postgres for tests. **`supbase/data.sql` is a prod data dump and must never be committed or used in tests.**

---

## 3. Design

### 3.1 Tenancy and roles

| Role | Who | Can |
|---|---|---|
| ECALT admin | `users.is_admin` | Create, suspend and terminate schools; set seats and budget; invite the first owner; support via audited impersonation |
| School owner / admin | `school_members.role in ('owner','admin')` | Everything inside the school: settings, DPA, staff, students, classes, all courses, all analytics. The owner can't be removed while they are the only owner |
| Teacher | `school_members.role='teacher'` | Create courses (in the school library), create classes (becoming lead), manage classes they teach, assign courses, view their classes' progress, reset their students' secrets. Can create students only if `settings.teachers_can_create_students` |
| Student | `users.profile_type='school_student'` | Learn assigned courses (D5) |

- Staff are ordinary ECALT **accounts** (adult Google sign-in). One person can belong to several schools; the UI has a school switcher.
- **Course edit rights (v1):** the course creator and school admins can edit and publish. Other teachers can view, duplicate (into their own copy) and assign. A `course_collaborators` table is backlog.
- All staff APIs are **path-scoped**: `/api/v1/schools/{school_id}/…`. Membership is checked once per request. Every child resource is fetched **with** the school id in the SQL (`WHERE id = %s AND school_id = %s`). That rule is what prevents IDOR, and `TESTING.md` §4 enforces it.
- **Cross-tenant access returns 404** (never reveals that something exists). Same-tenant access with too low a role returns 403 `school_role_required`.

### 3.2 Data model — migration `014_schools.sql`

Additive and idempotent, so it can be applied before the code deploys. Every new table gets `ENABLE ROW LEVEL SECURITY` with no policies (the backend connects as owner; this blocks PostgREST, same as `001_security_hardening`). Below is a sketch; the final DDL is `migrations/014_schools.sql` (SC-101). **As built:** link tables (`class_teachers`, `class_enrollments`, `course_sources`, `course_assignments`) also carry `school_id` and reference their parents through `(id, school_id)` composite foreign keys (and `school_courses` references `journeys(id, school_id)`), so the database itself rejects a link between two schools. Every foreign key to `users` is `SET NULL` or `CASCADE`, so the existing account-deletion cascade still completes. The backend code reads `journeys.school_id`, so **apply 014 before deploying the M1 backend**.

```sql
-- Tenants
schools(id uuid pk, name, slug unique, country char(2), status ['onboarding','active','suspended','terminated'],
        seat_limit int, monthly_ai_budget_cents numeric, settings jsonb default '{}',
        dpa_version text, dpa_accepted_at timestamptz, dpa_accepted_by text → users,
        created_at, updated_at, terminated_at)
school_members(school_id → schools, uid → users, role ['owner','admin','teacher'], status ['active','removed'],
               created_at, removed_at, pk(school_id, uid))
school_invites(id, school_id, email, role, token_hash, invited_by, expires_at, accepted_at, accepted_uid)

-- Students (a users row with profile_type='school_student', uid 'stu_<hex>', email NULL)
school_students(uid pk → users, school_id, display_name, external_ref, grade,
                status ['active','archived'], secret_kind ['picture','pin'], secret_hash,
                failed_attempts int, locked_until, badge_token_hash, created_by, created_at, archived_at,
                unique(school_id, external_ref))

-- Classes
classes(id, school_id, name, grade, subject, academic_year, join_code unique, settings jsonb,
        created_by, created_at, archived_at)
class_teachers(class_id, uid, role ['lead','co'], pk(class_id, uid))
class_enrollments(class_id, student_uid, enrolled_at, removed_at, pk(class_id, student_uid))

-- Courses (published state lives in journeys + step_content; drafts live here)
school_courses(journey_id pk → journeys, school_id, status ['draft','published','archived'],
               published_version int, created_by, created_at, updated_at, archived_at)
course_versions(id, journey_id, version int, state ['draft','published','superseded','discarded'],
                revision int,           -- optimistic lock for concurrent editors
                meta jsonb,             -- title, description, icon, tags, difficulty, age_group, estimated_hours
                steps jsonb,            -- [{id, title, description, type, estimated_minutes, core_question,
                                        --   body_md, quiz_anchors, citations:[{document_id, chunk_id, pages}],
                                        --   origin ['ai','teacher','ai_edited'], flags:[…]}]
                base_version int, change_summary, created_by, created_at, published_by, published_at,
                unique(journey_id, version))
  + unique index one_draft_per_course ON course_versions(journey_id) WHERE state = 'draft'
course_change_proposals(id, journey_id, version, op ['add','modify','remove','move'], step_id,
                        payload jsonb, reason, status ['pending','accepted','rejected'], decided_by, decided_at)

-- Source material
source_documents(id, school_id, uploaded_by, filename, mime, size_bytes, sha256, storage_path, page_count,
                 language, status ['pending_upload','uploaded','extracting','ready','needs_ocr','failed','deleted'],
                 error_code, created_at, deleted_at)
document_chunks(id, document_id, ordinal, heading_path text[], page_start, page_end, text, char_count)
course_sources(journey_id, document_id, added_at, pk(journey_id, document_id))

-- Delivery, jobs, money, audit
course_assignments(id, class_id, journey_id, assigned_by, assigned_at, due_at, status ['active','archived'],
                   settings jsonb)   + unique(class_id, journey_id) WHERE status='active'
school_jobs(id, school_id, kind ['extract','ocr','outline','build','regenerate_step','propose_update'],
            status ['queued','running','succeeded','failed','cancelled'], payload jsonb, progress jsonb,
            attempts, locked_at, locked_by, error, created_by, created_at, finished_at)
school_usage(school_id, period_start date, cost_cents numeric, input_tokens, output_tokens, pk(school_id, period_start))
school_audit_log(id bigserial, school_id, actor_uid, action, target_type, target_id, meta jsonb, created_at)

-- Changes to existing tables
ALTER TABLE journeys ADD COLUMN school_id uuid REFERENCES schools(id);
ALTER TABLE journeys ADD CONSTRAINT journeys_school_private CHECK (school_id IS NULL OR marketplace_status = 'private');  -- D11
CREATE INDEX ON journeys (school_id) WHERE school_id IS NOT NULL;
ALTER TABLE step_content ADD COLUMN source text NOT NULL DEFAULT 'ai' CHECK (source IN ('ai','school_published')),
                         ADD COLUMN locked boolean NOT NULL DEFAULT false;
ALTER TABLE users DROP CONSTRAINT users_profile_type_check,
                  ADD CONSTRAINT users_profile_type_check CHECK (profile_type IN ('account','profile','school_student'));
```

- **School courses have `journeys.uid = NULL`.** The school owns them, not the teacher, so account deletion (gap 4) can't touch them. The creator is stored in `school_courses.created_by`.
- Storage: a new **private** bucket `school-materials`. Paths look like `{school_id}/{document_id}/original.{pdf|docx}`.

### 3.3 Identity and sign-in

**Staff:** normal Google sign-in. An invite (`school_invites`, token stored as a hash, 7-day expiry) is accepted at `/school-invite?token=`. The page calls `POST /school-invites/preview {token}` (no sign-in) and `POST /school-invites/accept {token}`; the token travels in the body so it never lands in a request log. The **verified** email in the Firebase token claims must match the invited email (or an admin re-issues the invite to another address), and only adult accounts can join as staff. Re-inviting an address revokes its earlier link.

**Students (D1):**
1. Student opens `/class` and enters the class **join code** (8 characters from an alphabet without look-alike letters, rotatable by the teacher).
2. `GET /school-login/classes/{code}` returns the class name plus a roster of `{uid, display_name (first name + last initial), avatar, secret_kind}`. A school setting `login_roster_visible=false` switches the picker to typed usernames for older students.
3. The student enters their secret: a **picture password** (sequence of 3 icons from a 16-icon set) or a **6-digit PIN**. Secrets are scrypt-hashed (`profile_service.hash_pin`).
4. `POST /school-login/sessions {class_code, student_uid, secret}` returns a **Firebase custom token** (RS256, `uid=stu_…`, claims `{school_id, kind:'school_student'}`, 1 h expiry). The frontend calls `signInWithCustomToken`. From then on every request carries a normal Firebase ID token, so `core/auth.py` needs no second auth path.
5. **QR badge:** each student has a long random badge token (stored as a hash, rotatable). `POST /school-login/badge {token}` returns the same custom token. The teacher prints badges from the login-cards page.

**Abuse controls:** 5 wrong secrets lock that student for 15 min (`423 student_locked`). Too many failures on one class code throttle the code. All limits key on **student / class**, never IP (gap 6). Every lockout is logged to `school_audit_log`.

**Session policy:** student sessions use `browserSessionPersistence` (shared classroom devices). The backend enforces a maximum session age from the token's `auth_time` (`SCHOOL_STUDENT_SESSION_HOURS=12`) → 401 `school_session_expired`. Deleting a student also purges their Firebase record (`firebase_admin`).

**Bootstrap:** `POST /users` for a `stu_` uid returns immediately with `account_kind:'school_student'` plus school and student info. No birth-year gate, consent gate or onboarding modal. Consent is the school authorization recorded when the student was created: `consent_events(action='granted', method='school_authorization', details={school_id, dpa_version})`.

### 3.4 Authorization

New module `core/school_auth.py`:
- `require_school_member(school_id, roles=…)` — returns `SchoolCtx(uid, school_id, role)`. Membership is cached 60 s; `invalidate_school_member_cache(...)` runs on any membership change. Checks `schools.status` (suspended → 403 `school_access_suspended`, terminated → 404).
- `require_class_staff(ctx, class_id)` — school admin, or a teacher in `class_teachers`.
- Scoped loaders `load_class(ctx, class_id)`, `load_student(ctx, uid)`, `load_course(ctx, journey_id)`, `load_document(ctx, doc_id)`. Each one includes `school_id` in its `WHERE` clause and raises 404.

**Student route allowlist (fail-closed).** Inside `get_signed_in_uid` (as built — the root of every authenticated dependency, including the account-holder ones): if the resolved uid is a `stu_` uid, the request's route template + method must be in `STUDENT_ALLOWED_ROUTES`, otherwise 403 `school_student_not_allowed`. A route added later is therefore **denied to students by default**. A test enumerates `app.routes` and fails if any route is unclassified (`TESTING.md` §5); routes that read the token by hand (today only `POST /users/claim`, which now refuses `stu_` logins) are listed separately. Allowed routes in v1:
- bootstrap: `POST /users`, `GET /users/me`
- `GET /school-student/home`
- for **assigned** journeys only: `GET /journeys` (returns only assigned published courses), `GET /journeys/{id}`, step content GET, step visual + visual events, progress GET/POST/DELETE, quiz generate (assigned step required) / step-status / hint / submit, step feedback (stored, never triggers regen). Quiz skip is not allowed until SC-503 decides it per class.
- journey tutor chat (`POST /chat/stream` with `interaction_type=journey_tutor` and an assigned `journey_id`; per-class on/off arrives in SC-503)

Account-level dependencies (`get_account_holder`, `get_parent_session`, …) also reject school students outright. That is a second layer behind the allowlist.

**Journey access (`services/journey_access.py`).** `assert_can_read_journey(uid, journey_id)`:
- `school_id IS NULL` → current behaviour (unchanged for non-school users; a school student is denied by D5).
- `school_id` set → allowed if the viewer is staff of that school, or a student with an **active enrollment** in a class that has an **active assignment** of that journey. Anyone else gets 404. Cached 60 s per `(uid, journey_id)`.
- Applied to every endpoint that takes a `journey_id` (list in SC-107).

`assert_account_active` additionally blocks a student who is archived or whose school is suspended or terminated (403 `school_access_suspended`), with the same fail-closed cache.

### 3.5 Course lifecycle and invariants

```
upload docs ─▶ extract ─▶ OUTLINE job ─▶ teacher edits/approves outline ─▶ BUILD job ─▶ DRAFT (editable)
                                                                                      │
                     published journeys row + locked step_content  ◀── PUBLISH ◀──────┘
                     (what students see; versions v1, v2, …)
```

- A course gets its `journeys` row (`school_id`, `uid NULL`) and `school_courses` row **when it's created**. `journeys.steps` is written **only on publish**, so students and assignments only ever see the published version. Drafts live in `course_versions`.
- **Publish** runs in one transaction:
  1. Validate: at least one step, every step has a `body_md`, no build job running, revision matches.
  2. Write `journeys` meta and steps.
  3. Upsert `step_content` for every step with `source='school_published', locked=true`, plus `quiz_anchors`.
  4. Mark the version `published` and the previous one `superseded`.
  5. Invalidate cached quiz sets for changed steps.
  6. Write the audit log.
- **Invariants** (each has tests, `TESTING.md` §1):
  - **I4:** students never see AI content a teacher hasn't published.
  - **I5:** nothing automatic overwrites `locked` step content. `upsert_step_content` refuses to touch locked rows unless the caller is the publish path. Lazy prompt-version regen, the regenerate endpoint, feedback regen and `warm_journey_steps` all skip school journeys. A cache miss on a school journey returns 409 `content_not_published` and never generates.
  - **Step ids stay stable** across versions, so `user_progress` stays valid (§3.8).

### 3.6 Document ingestion

1. **Upload:** `POST /schools/{sid}/documents/upload-url {filename, size_bytes, mime}` checks the extension (`.pdf`, `.docx`) and size (`SCHOOL_DOC_MAX_MB=25`), creates a `source_documents` row, and returns a **Supabase signed upload URL**. The browser uploads **directly to Storage**, which avoids the Vercel-rewrite → Railway request-size ceiling (exact limit confirmed in spike SC-008). The CSP `connect-src` in `frontend/vercel.json` must allow the Supabase origin. `.doc` and `.docm` are rejected with a "save as .docx or PDF" message.
2. **Complete:** `POST …/documents/{id}/complete` downloads the object and verifies size, **magic bytes** (`%PDF-`; a ZIP containing `word/document.xml` and no `vbaProject.bin`) and sha256 (deduplicated within the school). It then enqueues an `extract` job.
3. **Extract**, in a **sandboxed subprocess** (wall-clock timeout 120 s, `RLIMIT_AS` memory cap) so a hostile PDF can't hang or crash the API:
   - PDF: `pypdf` (new dependency, pure Python) extracts text per page. Encrypted files are rejected. Page cap: `SCHOOL_DOC_MAX_PAGES=300`.
   - DOCX: `python-docx` (new dependency). Heading styles become structure, tables become markdown, images are ignored in v1. Before parsing, the ZIP is guarded (≤100 MB uncompressed, ≤5,000 entries) and entity resolution stays off (XXE).
   - Quality checks: if more than 30 % of pages are near-empty, the document is **scanned** → `needs_ocr`. If the share of valid Unicode word characters is too low (broken Devanagari font encodings, for example), the text is **garbled** → `needs_ocr`.
4. **Structure and chunking:** repeated headers and footers are stripped. Chunks follow section boundaries with a `heading_path`, `page_start`/`page_end`, and roughly 1.5–2.5k tokens each → `document_chunks`. A cap of `SCHOOL_DOC_MAX_CHARS=400k` applies.
5. **OCR (M3b, `SCHOOL_DOC_OCR_ENABLED`):** a new interaction type `document_ocr` sends page images or the PDF to a vision-capable model. Its cost is charged to the school.
6. **Retention:** originals stay while any course cites them. A school setting can delete originals N days after extraction (chunks are kept). Deleting a document removes the storage object and its chunks; published courses keep their content.

### 3.7 AI course builder (grounded generation)

New interaction types in `provider_service`: `school_course_outline`, `school_step_content`, `school_faithfulness_critic` (+ `document_ocr`). Each gets a code default and an **`ai_provider_config` row in the DB** (per the prompt-storage rule: prod reads the DB). New models also go into `COST_PER_TOKEN`.

- **Teacher inputs:** grade, subject, course goal, number of steps or session length, language of instruction, "follow document order" (default on).
- **Outline job:** input is the heading tree plus section summaries (within a token budget) and the teacher inputs. Output: course meta plus steps `{title, description, type, estimated_minutes, core_question, learning_objective, chunk_ids[]}` and `skipped_sections[{heading, reason}]`. **The response is validated:** every step cites at least one real chunk id, and every top-level section is either cited or listed as skipped. On a validation failure the job retries once, then fails visibly. The teacher **reviews and edits the outline before any step content is generated** (this saves cost and catches structure problems early).
- **Build job:** generates step bodies in parallel (`SCHOOL_GENERATION_CONCURRENCY=4`), reusing `generate_step_content`'s context mechanics (outline, position, covered facts). The new grounded contract: *teach what the cited source says; analogies and age-appropriate explanation are fine; no new factual claims; mark any added general knowledge.* Quiz anchors come from source facts. Output is the existing step-content JSON plus `citations`.
- **Critic:** checks claims against the cited chunks. Unsupported claims get one revision pass. Whatever remains becomes `flags` that the editor shows as "Check this" highlights. Students never see flags.
- **Untrusted input:** document text sits inside explicit delimiters and is labelled as data. Output must parse against the schema; links, HTML and scripts are stripped from bodies; `content_filter` runs on the output. The **mandatory teacher review before publish** is the final control (I9).
- **Cost:** before an outline or build job starts, the API returns an **estimate** (from chunk token counts) and checks the school budget. Every model call records usage against the school (§3.10). Job progress (`steps_done/steps_total`) lives in `school_jobs.progress`, which the UI polls.
- **Editor operations:** edit any field (`body_md` uses the existing markdown dialect rendered by `MarkdownContent`), add, delete, reorder, regenerate one step with an instruction (grounded), "simplify for younger readers", and preview as a student. Editing sets `origin='teacher'` (or `ai_edited`). Regenerating a teacher-edited step requires `overwrite_teacher_edits=true`. Each write sends `revision`; a mismatch returns 409 `draft_conflict`.

### 3.8 Updating a course from a new document

Three modes: **revise** (a new edition of the same material), **supplement** (add material from another document), **replace** (build a fresh draft from the new document; keep step ids where titles match).

1. Extract the new document (§3.6).
2. **Align** new chunks to each step's cited chunks, using heading-path match first and then lexical similarity (token Jaccard / `difflib`; no embeddings dependency in v1). Each step is classified as *unchanged*, *source changed*, or *source removed*. New sections that no step covers are collected.
3. **Propose** a change set in `course_change_proposals`: `modify` (new body + diff + reason), `add` (position + full step), `remove` (reason), `move`. Steps with `origin='teacher'` are **never** auto-modified; for those the proposal is a suggestion only.
4. The teacher accepts or rejects each item (or accepts all). Accepted items produce a **new draft version** based on the published one.
5. **Publish v(n+1). Progress rules:**
   - Modified steps keep their id, so completion is kept. A student who finished the old version sees an "Updated since you finished" badge.
   - Removed steps drop out of the journey; their `user_progress` rows are kept but don't count toward completion.
   - Added steps appear as not done.
   - Quiz sets for modified steps are invalidated.
   - Version history lists every version. **Restore** copies an old version into a new draft (it never rewrites history).

### 3.9 Classroom delivery

- **Assignments:** a teacher of the class (or a school admin) assigns a **published** course to a class, with optional `due_at` and settings (`tutor_enabled`, `quiz_required`). Archiving an assignment hides the course from students; their progress is kept.
- **Student home:** `GET /school-student/home` returns classes → assignments with progress, due dates and teacher name. For a student, `GET /journeys` returns only their assigned courses.
- **Settings precedence:** class setting > school setting > default.
  - `tutor_enabled`: default **on** for grade 8+ and **off** below, until D4 is confirmed.
  - `content_age_band`: derived from grade (≤ grade 5 → `kids`, 6–9 → `teens`, 10+ → `teens`/`adults` per school) and passed to tutor, quiz and visual generation.
  - Open explore, spark and general chat are **off** (D5).
- **No commercial surface for students:** no pricing, upgrade prompts, marketplace, notifications, WhatsApp or email (students have no email). Every scheduler and notification audience query gets `profile_type = 'account'` (most already filter that way since family profiles; SC-506 verifies all of them).

### 3.10 Billing and budgets (D2)

- `schools.monthly_ai_budget_cents` and `seat_limit` are set by an ECALT admin. Creating a student fails with 409 `seat_limit_reached` when active students would exceed the limit.
- `check_budget(uid, …, school_id=None)`: for a `stu_` uid the school is implied; staff endpoints under `/schools/{sid}` pass `school_id`. With a school context the check compares `school_usage` for the current month against the school budget. `record_usage` gets an optional `school_id` and also increments `school_usage`. Student usage still updates the per-uid `token_usage` row for analytics.
- **Per-student daily caps** (tutor messages and quiz generations per day, school-configurable) stop one student from draining the pool.
- When exhausted: students get 402 `school_budget_exhausted` ("Ask your teacher") and staff get a banner. School admins get an email at 80 % and 100 % (deduplicated per month).

### 3.11 Teacher analytics

- **Class progress matrix** (in M5): students × assigned courses → steps done/total, last active, average quiz score, overdue flag.
- **Student drill-down** (M7): per-step completion, quiz attempts and hints (`quiz_results`, `quiz_sessions`), tutor transcript if allowed (D4), with the disclosure shown to the student.
- **Struggling flags** (M7): quiz accuracy below 50 % across the last 3 sets, or no activity for 7 days with a due date within 3 days.
- **CSV export** (M7) escapes cells starting with `= + - @` (formula injection). A weekly teacher digest is sent by a prod-only scheduler job.

### 3.12 Compliance and data lifecycle (legal review is a launch blocker)

- **Roles:** the school is the data controller and ECALT the processor. The **DPA** must be accepted (`/schools/{sid}/dpa/accept`) before any student can be created (409 `dpa_required`). Legal basis by jurisdiction (SC-002): India DPDP Act + Rules (educational-institution provisions), US COPPA school-authorization + FERPA school-official, GDPR Art. 28. **Counsel must confirm the scope for each before real student data is accepted.**
- **Data minimisation:** students have a display name (first name + last initial is recommended in the UI), grade, optional school reference number, and **no email, birth date or photo**.
- Each student's creation is recorded as a `consent_events` `school_authorization` entry. Every staff mutation and every access to student detail is written to `school_audit_log`.
- **Archive:** at year end, a bulk archive blocks login and keeps data. **Delete:** `account_service` cascade + Firebase purge + enrollments. **Export:** per student (reuses `build_user_export`) and per class (CSV).
- **Offboarding:** school `terminated` → 30-day grace → a deletion job removes students, courses, documents, storage objects and usage, keeping only the audit trail and pseudonymised consent events (same as today's policy).
- **Copyright:** the school terms say the school warrants it has rights to the material it uploads. Material stays private to the school and is never used outside it (D11).
- Update `docs/children-data-dpia.md` with a schools section (shared devices, teacher visibility, uploaded documents that may contain student PII).

### 3.13 Background jobs

`services/school_jobs.py`: a DB-backed queue (`school_jobs`). An **in-process worker** starts in `main.py` lifespan when `SCHOOL_JOBS_WORKER_ENABLED=true`, independent of `SCHEDULER_ENABLED`, so dev processes jobs too. It claims work with `SELECT … FOR UPDATE SKIP LOCKED` (safe if Railway ever runs more than one replica).
- Jobs are idempotent and have per-kind handlers. Attempts are capped at 3 with backoff.
- **Stale-lock recovery:** a `running` job with `locked_at` older than 10 min is re-queued, which covers jobs lost to a redeploy (gap 7).
- Jobs can be cancelled (`cancelled`); a running handler checks for cancellation between steps.
- Concurrency per school (2) and globally (`SCHOOL_JOBS_MAX_CONCURRENCY=4`).
- Local dev talks to the prod DB, so **keep the worker off locally** unless pointed at a local DB, the same rule as the scheduler.

### 3.14 Configuration

| Setting | Default | Notes |
|---|---|---|
| `SCHOOLS_ENABLED` | `False` | When off, `/schools`, `/school-login` and `/school-student` return 404 |
| `SCHOOL_JOBS_WORKER_ENABLED` | `False` | Turn on for Railway dev + prod |
| `SCHOOL_JOBS_MAX_CONCURRENCY` | `4` | |
| `SCHOOL_GENERATION_CONCURRENCY` | `4` | Parallel step builds per job |
| `SCHOOL_DOC_MAX_MB` / `SCHOOL_DOC_MAX_PAGES` / `SCHOOL_DOC_MAX_CHARS` | `25` / `300` / `400000` | |
| `SCHOOL_DOC_OCR_ENABLED` | `False` | M3b |
| `SCHOOL_MATERIALS_BUCKET` | `school-materials` | Private bucket |
| `SCHOOL_STUDENT_SESSION_HOURS` | `12` | Max age from `auth_time` |

New dependencies: `pypdf`, `python-docx`. Test-only: `reportlab` (fixture generation) in a new `requirements-dev.txt`.

### 3.15 API surface (v1)

All routes are under `/api/v1`. `{sid}` = school id. **Bold** = ECALT admin only.

| Group | Endpoints |
|---|---|
| Admin (built) | **`POST/GET /admin/schools`, `GET/PATCH /admin/schools/{sid}`** (name, status, seats, budget), **`POST /admin/schools/{sid}/owner-invite`** |
| Membership (built) | `GET /schools/mine`, `POST /school-invites/preview`, `POST /school-invites/accept`, `GET/PATCH /schools/{sid}`, `POST /schools/{sid}/dpa/accept` (owner), `GET /schools/{sid}/staff`, `POST /schools/{sid}/staff/invites`, `DELETE /schools/{sid}/staff/invites/{invite_id}`, `PATCH/DELETE /schools/{sid}/staff/{uid}` (DELETE on yourself = leave) |
| Students | `GET/POST /schools/{sid}/students` (paged, `?q=&class_id=&status=`), `POST …/students/import?dry_run=`, `PATCH/DELETE …/students/{uid}`, `POST …/students/{uid}/reset-secret`, `POST …/students/{uid}/archive` + `/restore`, `POST …/students/{uid}/rotate-badge`, `GET …/students/{uid}/export` |
| Classes | `GET/POST /schools/{sid}/classes`, `GET/PATCH/DELETE …/classes/{cid}`, `POST/DELETE …/classes/{cid}/teachers[/{uid}]`, `POST/DELETE …/classes/{cid}/students[/{uid}]`, `POST …/classes/{cid}/rotate-code`, `GET …/classes/{cid}/login-cards` |
| Documents | `POST /schools/{sid}/documents/upload-url`, `POST …/documents/{did}/complete`, `GET …/documents[/{did}]`, `DELETE …/documents/{did}` |
| Courses | `GET/POST /schools/{sid}/courses`, `GET …/courses/{jid}`, `GET/PATCH …/courses/{jid}/draft`, `POST …/draft/steps`, `PATCH/DELETE …/draft/steps/{step_id}`, `POST …/draft/reorder`, `POST …/draft/steps/{step_id}/regenerate`, `POST …/courses/{jid}/outline/approve`, `POST …/courses/{jid}/publish`, `GET …/courses/{jid}/versions`, `POST …/versions/{v}/restore`, `POST …/courses/{jid}/duplicate`, `POST …/courses/{jid}/archive`, `POST …/courses/{jid}/estimate` |
| Updates | `POST /schools/{sid}/courses/{jid}/updates` (`mode`, `document_ids`), `GET …/updates/{job_id}/proposals`, `POST …/proposals/{pid}/accept` / `reject`, `POST …/proposals/accept-all` |
| Jobs | `GET /schools/{sid}/jobs/{job_id}`, `POST …/jobs/{job_id}/cancel` |
| Assignments | `GET/POST /schools/{sid}/classes/{cid}/assignments`, `PATCH/DELETE …/assignments/{aid}` |
| Analytics | `GET /schools/{sid}/classes/{cid}/progress`, `GET …/classes/{cid}/students/{uid}`, `GET …/classes/{cid}/progress.csv`, `GET /schools/{sid}/usage` |
| Student login | `GET /school-login/classes/{code}`, `POST /school-login/sessions`, `POST /school-login/badge` (all public, keyed rate limits) |
| Student | `GET /school-student/home` + the allowlisted learner routes (§3.4) |

New error codes (structured `detail.error`): `school_role_required`, `school_access_suspended`, `school_student_not_allowed`, `school_session_expired`, `class_code_invalid`, `invalid_student_secret`, `student_locked`, `seat_limit_reached`, `dpa_required`, `document_rejected` (+ `reason`), `draft_conflict`, `content_not_published`, `course_not_published`, `school_budget_exhausted`. Added in M1: `school_not_found`, `content_locked` (regenerate on a school course), `invite_invalid`, `invite_expired` (410), `invite_email_mismatch`, `invite_not_found`, `member_not_found`, `staff_must_be_adult`, `account_setup_required`, `already_member`, `last_owner`, `invalid_role`, `invalid_email`, `invalid_settings`, `dpa_version_mismatch`, `school_terminated`.

---

## 4. Milestones

Tickets, dependencies and status are in `TRACKER.md`. Each milestone has to pass its **release gate** (`TESTING.md` §9) before the next one builds on it.

| # | Milestone | Outcome | Gate highlights |
|---|---|---|---|
| M0 | Foundations | Decisions made, legal track started, pilot school, **test harness + CI**, risk spikes (extraction, upload path, custom tokens) | CI green on new suites; spike report |
| M1 | Tenancy + hardening | Schools, staff, invites, `school_auth`, student allowlist, **journey access control + leak fixes + regen guards** | Authz matrix (staff), invariants I1/I3/I5/I6 |
| M2 | Students, classes, login | Roster CRUD + CSV import, classes, codes, picture/PIN/QR login, custom tokens, sessions | I2/I7, lockout and session tests, legal sign-off before real students |
| M3 | Document ingestion | Signed upload, validation, sandboxed extraction, chunking, job worker (M3b: OCR) | I8 upload-security corpus 100 % |
| M4 | AI course builder | Outline → approve → build → edit → publish, versions, critic flags | I4/I9, **AI eval thresholds** |
| M5 | Classroom delivery — **pilot-ready MVP** | Assignments, student home, settings, school budget pool, basic progress | E2E smoke, load (classroom burst), security review pass 1 |
| M6 | Course updates from documents | Align → propose → review → publish v(n+1) with progress rules | I10, update-eval thresholds |
| M7 | Teacher analytics | Drill-down, struggling flags, transcripts (D4), CSV, digest, usage | Export safety, analytics query perf |
| M8 | Launch hardening | Security review, load, offboarding and deletion, legal copy, observability, runbook, rollout | All gates; pilot sign-off |

Rollout: dev (`SCHOOLS_ENABLED=true`) → prod with only the pilot school created (the flag is on, but schools exist only when an admin creates them) → GA.

---

## 5. Top risks (full register in `TRACKER.md`)

1. **Student-data compliance.** Real student data waits for counsel sign-off (SC-002 blocks the M2 go-live).
2. **Unfaithful AI content reaching children.** Mitigated by grounded prompts, citations, the critic, mandatory teacher review and eval gates.
3. **Tenant leakage through existing journey endpoints.** Fixed by SC-107/108 and the invariant tests in M1, *before* any school data exists.
4. **Teacher work overwritten by automatic regeneration.** Fixed by SC-109 (`locked` content).
5. **Hostile or odd uploads.** Mitigated by the sandboxed extraction subprocess, limits and the fixture corpus.
6. **Classroom traffic patterns** (one NAT IP, bursts at bell time, shared devices). Mitigated by keyed limits, load tests and session policy.

---

## 6. Open questions / later

- Course collaborators (multiple editors) and a school-wide "approved course" workflow (head-of-department review before publish).
- Parent link for school progress (D6) and how it interacts with family profiles.
- Embeddings-based alignment for updates, if lexical alignment misses too much (measured by the M6 eval).
- Classroom "live mode" (teacher paces steps for the whole class).
- Google Classroom roster sync and assignment push.
