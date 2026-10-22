# Schools & Teacher-Built Courses — Frontend Changes

> This is the frontend contract for the backend plan in `README.md`. Ticket ids refer to `TRACKER.md`. Build each section alongside its backend milestone. Everything stays invisible until the backend's `SCHOOLS_ENABLED=true` and a school exists.
>
> **Status (2026-10-12):** M1 and M2 are **implemented** on both sides and pushed to `feature/dev` (migration 014 applied to the Supabase project). M1: `account_kind` in `AuthContext` (§1), `SchoolContext` + nav entry + staff area `/school` (§2–3), DPA modal, `/school-invite`, admin **Schools** tab (§11), `lib/schoolApi.ts` (§13), error messages (§14). M2: students + CSV import (§4), classes + printable login cards (§5), `/class` sign-in, `/class/badge`, student shell `/my-classes` (§6) — QR codes on cards wait for the `qrcode` dependency (§15). Sections marked *(as built)* describe the real API. Documents, the course builder, assignments and analytics (M3+) are still the plan.

## 0. Ground rules

- All school calls go through a new **`lib/schoolApi.ts`** using `request()` from `api.ts`, so `authHeaders()` and structured errors work unchanged. The school id is a path parameter; there is **no new header**.
- Staff never send `X-Profile-Id` on `/schools/*` calls (the API answers 403 `parent_profile_required`). If the device has an active child profile, the staff shell shows "Switch to your own profile to manage your school".
- Staff routes act like other parent-only routes: when the staff member's account has family profiles they need the parent PIN unlock (`X-Parent-Unlock`). `request()` already handles 403 `parent_unlock_required` by opening the PIN prompt and retrying. `GET /schools/mine` and the invite routes don't need the unlock.
- Reuse the learner UI for students: the `Journey` page, `StepNode`, `QuizCard`, `JourneyTutor`, `MarkdownContent`. No second course player.
- Follow the existing gates: `npm run build` (tsc) must pass. Check light + dark, 375 px **and 1024 px** (school Chromebooks/tablets), keyboard navigation and slow networks.
- **Config changes in `vercel.json` (blocking):**
  - CSP `connect-src` must include the Supabase project origin (`https://<project-ref>.supabase.co`), or direct uploads (§7) fail.
  - `Permissions-Policy` currently says `camera=()`. That blocks QR-badge scanning (§6.3); change it to `camera=(self)`.

## 1. Account kinds and auth (SC-105, SC-207, SC-208)

- *(as built)* `POST /users` and `GET /users/me` return **`account_kind: 'account' | 'profile' | 'school_student'`** for everyone. School students also get `school: {id, name}` and `student: {display_name, grade, classes: [{id, name, grade, subject}]}`, `onboarding_done: true`, `needs_birth_year: false`, `email: null`. For a student `POST /users` ignores the body. An archived student or a suspended school gets 403 `school_access_suspended` from `POST /users`.
- *(as built)* A student's `GET /journeys` returns only the published courses assigned to their active classes (no curated or community journeys). Any route outside the student allowlist answers 403 `school_student_not_allowed`.
- `AuthContext`:
  - New `signInWithClassToken(customToken)` → `setPersistence(auth, browserSessionPersistence)` then `signInWithCustomToken(auth, customToken)`. Only students use session persistence; staff and families keep the current persistence.
  - For `school_student`, the post-sign-in phase machine is **skipped**: no birth-year gate, consent screens, `OnboardingModal` or `ReconsentBanner`. Phase = `none`.
  - Expose `accountKind` and `isSchoolStudent`.
  - On 401 `school_session_expired`: sign out → `/class` with "Your session ended — sign in again".
- `ProfileProvider` does nothing for school students (no picker, no PIN).
- `SubscriptionProvider` doesn't call `/subscriptions/me` for students. Budget errors come from 402 `school_budget_exhausted` instead (§14).

## 2. School context and staff shell (SC-114)

- `lib/SchoolContext.tsx`: *(as built)* `GET /schools/mine` → `{schools: [{id, name, slug, status, role}]}` (terminated schools are left out). Holds `activeSchoolId` (localStorage `ecalt.activeSchool`, read and written in try/catch) and exposes `role`, `can(action)` helpers that mirror the matrix in `TESTING.md` §4. The UI hides what the API would reject; the API remains the authority.
- Show a **"School"** nav entry only when `/schools/mine` is non-empty. A school switcher appears when the user belongs to more than one school.
- Staff shell layout: left rail (Dashboard, Classes, Students, Courses, Documents, Staff*, Settings*, Usage*; `*` = admin only) and a content area. On mobile the rail collapses into a drawer.
  - *(as built, M1)* `pages/school/SchoolLayout.tsx`: header (school name, status chip, "You're a teacher here", school switcher when there are several), then a horizontal tab bar (Dashboard · Staff · Settings) that scrolls on narrow screens — the same pattern as the admin page. Switch to the rail when Classes/Students/Courses/Documents arrive and the tab count grows. Child pages get `{school, setSchool, reload}` through `useSchoolPage()` (outlet context). Teachers see Settings read-only.
  - *(as built)* `/school` and `/school-invite` are parent-only for `KidModeGuard`; `/school-invite` is exempt from the profile-picker redirect so an invite link opened on a family device still works.
- Suspended school → full-page notice (403 `school_access_suspended`).
- **Dashboard (`/school`)**: my classes (cards with student count + active assignments), recent courses with status chips (Draft / Building… / Published vN), running jobs, budget meter (admins).
  - *(as built, M1)* DPA banner (owner: "Review & accept"; others: waiting for the owner), stat cards (staff, students / seats, monthly AI budget for admins), a "Getting started" checklist (accept the DPA, invite teachers) and a one-line "coming next" note. Classes, courses and jobs join the dashboard with their milestones.

## 3. Settings, DPA, staff (SC-111..113)

- **First-run checklist** for the owner: accept DPA → invite teachers → add students → create a class → create a course. Each step links to its page.
- *(as built)* `GET /schools/{sid}` returns the school with `my_role`, `settings` (all keys, defaults filled in), `status`, `seat_limit`, `staff_count`, `student_count`, `dpa_version`, `dpa_current_version`, `dpa_accepted`; `monthly_ai_budget_cents` only for owners/admins.
- **DPA:** *(as built — `components/school/DpaModal.tsx`; the modal shows a plain-language summary, **to be replaced by the counsel-approved text before real student data**, SC-002/SC-804)* owner only. A modal showing the agreement text, with an "I accept on behalf of {school}" checkbox → `POST /schools/{sid}/dpa/accept {dpa_version}` where `dpa_version` is the `dpa_current_version` the owner was shown. 409 `dpa_version_mismatch` (with `current_version`) means the text changed: reload it. Accepting moves an `onboarding` school to `active`. Any 409 `dpa_required` from student creation (M2) opens this modal. The DPA text itself is legal copy (SC-002) — not served by the API yet.
- **Settings (`/school/settings`)**: *(as built)* `PATCH /schools/{sid} {name?, settings?}` (owners/admins). `settings` is a partial object merged over the current one. Keys: `teachers_can_create_students` (bool), `login_roster_visible` (bool), `teacher_transcript_access` (bool), `delete_originals_after_days` (1–3650 or null), `student_daily_tutor_messages`, `student_daily_quiz_sets` (0–500). Unknown keys or bad values → 422 `invalid_settings` with `fields`.
- **Staff (`/school/staff`)**: *(as built)* `GET /schools/{sid}/staff` → `{members: [{uid, role, display_name, email, photo_url, created_at}], invites: [{id, email, role, expires_at, created_at, expired}]}` (`invites` is empty for teachers). Invite form → `POST …/staff/invites {email, role}` (201; admins can't invite owners). Revoke → `DELETE …/staff/invites/{invite_id}`. Change role → `PATCH …/staff/{uid} {role}`. Remove → `DELETE …/staff/{uid}`; the same call on yourself is "Leave school" (any role). 409 `last_owner` when it would leave the school without an owner; 409 `already_member` when inviting existing staff.
- **Invite accept (`/school-invite?token=`)**: *(as built)* read the token from the query string, then **remove it from the URL** (`history.replaceState`). `POST /school-invites/preview {token}` (no sign-in) → `{school_name, role, email_hint, expires_at}` for a "Join {school} as {role}" screen. After Google sign-in → `POST /school-invites/accept {token}` → `{school_id, school_name, role}` → set the active school and go to `/school`. Errors: 403 `invite_email_mismatch` ("This invite was sent to a***@school.org — sign in with that account"), 404 `invite_invalid` (used, revoked or unknown), 410 `invite_expired`, 403 `staff_must_be_adult`, 409 `account_setup_required` (finish the normal sign-up first).

## 4. Students (SC-201, SC-202, SC-204, SC-209, SC-210a)

- **List (`/school/students`)**: search, filter by class/grade/status, paged (server-side). Columns: name, grade, classes, last active, status. Row actions: edit, reset secret, rotate badge, archive/restore, export, delete (typed confirmation).
- **Add student**: name (hint: "first name + last initial is enough"), grade, optional school reference number, secret type (picture for grade ≤ 3 by default, otherwise PIN). On success, show the **secret once** with "Print login card". The secret can't be viewed later, only reset.
- **Import wizard**:
  1. Download a CSV template (`name, grade, external_ref, class`).
  2. Upload → `POST …/students/import?dry_run=true`.
  3. Report: row-level errors, duplicates (matched on `external_ref`), seat-limit overflow. The user can't continue while there are errors.
  4. Commit → summary + "Print login cards for N students".
- Seat meter: `active / seat_limit`. A 409 `seat_limit_reached` explains how to raise the limit (contact ECALT).
- *(as built — `pages/school/SchoolStudents.tsx`, `components/school/StudentImportWizard.tsx`)*:
  - `GET …/students?q=&class_id=&status=&limit=&offset=` → `{students, total, seat_limit, seats_used, can_manage}`; each student has `has_secret`, `has_badge`, `locked_until`, `classes`. "Show more" pages by 50.
  - Row actions: new sign-in (`POST …/students/{uid}/reset-secret` → secret shown once in `SecretReveal`; also clears a lockout), export (admins, downloads JSON), archive/restore, delete (inline confirmation). Status chips: Pictures / PIN / "No sign-in yet" / Locked.
  - Add student: default secret is a picture password up to **grade 4** (PIN after); teachers can only pick classes they teach. `POST …/students` returns `secret` (3 icon indices or a 6-digit string) and `badge_token` once.
  - Import: `POST …/students/import?dry_run=true|false` with JSON `{csv}` (the file is read in the browser; 1 MB / 2,000 rows). Header aliases: name; grade/std (KG/LKG/UKG = 0); roll number/admission no; class/section; sign-in (picture|pin). The report lists per-line errors and warnings; commit is blocked while any exist (422 `import_has_errors` carries the report). **Imported students get no secret yet** — the import summary tells staff to print each class's login cards.

## 5. Classes and login cards (SC-203, SC-206, SC-210a)

- **List + create (`/school/classes`)**: name, grade, subject, academic year.
- **Class page (`/school/classes/:classId`)** tabs: **Students** (enroll from roster with multi-select, remove), **Courses** (assignments, §9), **Progress** (§10), **Sign-in** (the join code shown large, "rotate code", co-teachers).
- *(as built — `pages/school/SchoolClasses.tsx`, `SchoolClassDetail.tsx`)*: class list split into "My classes" / "Other classes"; create (you become lead teacher); one detail page instead of tabs (Courses and Progress arrive with M5): join code shown large with "New code", edit name/subject/year, teachers (add co-teacher from staff, remove), students (search the roster to add, remove), "Print login cards", archive. Read access for all staff; changes for the class's teachers and admins (`can_manage`).
- *(as built — `pages/school/LoginCardsPrint.tsx` at `/school/print/cards/:classId`, outside the staff shell)*: secrets are stored hashed, so cards come from `POST …/classes/{cid}/login-cards {reset}`: "Cards for students without a sign-in" (`reset:false`) or "New sign-ins for the whole class" (`reset:true`, old cards stop working). Cards show school, class, `<host>/class`, the class code, avatar + name and the picture password (icons with names) or PIN; print via `window.print()` with `print:` styles. **No QR yet:** badge tokens are issued but not printed until the `qrcode` package is approved (§15).
- **Login cards (`/school/print/login-cards?classId=`)**: a print stylesheet with 8 cards per A4 page. Each card has the class code, the student's name, their picture password (icons) or PIN, a QR badge, and the URL `ecalt.app/class`. Secrets come from `GET …/classes/{cid}/login-cards`, which returns **only** freshly reset secrets; the page warns "Printing resets PINs for students who don't have one yet" when relevant. QR generation needs the **`qrcode`** npm package (new dependency, approval needed).

## 6. Student sign-in and student shell (SC-205..208, SC-210b)

### 6.1 `/class` sign-in (public)
1. **Class code** field: large, uppercase, auto-format `XXXX-XXXX`, uses the code's unambiguous alphabet. `GET /school-login/classes/{code}`; unknown code → `class_code_invalid`.
2. **"Who are you?"**: a grid of avatar + first-name tiles, or a typed username when the school hides the roster. Big tap targets.
3. **Secret**:
   - *Picture password:* a 4×4 grid of the 16 icons from `lucide-react` (cat, dog, fish, bird, sun, moon, star, tree-pine, flower-2, car, rocket, apple, heart, cloud, house, umbrella). The student taps 3; each icon has an accessible name. Icon ids are sent as the secret.
   - *PIN:* reuse `components/family/PinPad.tsx` (6 digits).
4. `POST /school-login/sessions` → `signInWithClassToken(token)` → `/my-classes`.

Errors: `invalid_student_secret` ("That's not quite right — try again"), `423 student_locked` ("Ask your teacher to help you sign in", with the unlock time for the teacher), `school_access_suspended`.

*(as built — `pages/ClassSignIn.tsx`)*: the last class code is remembered on the device (localStorage, convenience only). Roster names arrive as "First L.". When the roster is hidden the student types their **roll number** (`external_ref`) and can switch between PIN and pictures. Picture icons (`lib/pictureIcons.ts`, order is fixed — the backend stores indices): sun, moon, star, heart, tree, flower, fish, bird, cat, dog, apple, car, rocket, boat, house, umbrella; three taps submit automatically, with undo. Wrong secret → shake (motion-safe) + message. Also handled: `class_code_throttled` (429), `login_unavailable` (503, no Firebase service account), a signed-in adult on the device ("Sign out first"), `?expired=1`. `AuthContext.signInWithClassToken` sets `browserSessionPersistence` then `signInWithCustomToken`.

### 6.2 Student shell
- Minimal nav: **My classes**, the current course, the student's name, a prominent **Sign out**.
- Hidden for students: Home spark, Explore, Learn chat hub, Journeys browse, Marketplace, Passport, Mind signature, Pricing, Profile/privacy pages, Family, Admin. A **route guard** redirects any other route to `/my-classes`; the backend allowlist enforces this anyway.
- Show a "You're signed in on a shared device — sign out when you're done" hint on first load of a session.
- If transcripts are visible to teachers (D4), the tutor panel shows "Your teacher can see this chat".
- *(as built)*: `Navigation` renders a student variant (logo, My classes, theme, Sign out → `/class`) for `stu_` uids; `StudentGuard` (in `ProfileRouting.tsx`) redirects everything except `/my-classes`, `/journey/:id`, `/class*` and the legal pages. Profile, subscription, reconsent and school-staff lookups are skipped for students (no 403 noise). `pages/StudentHome.tsx` (`/my-classes`) lists assigned courses from `GET /journeys` with step progress; due dates and per-class grouping come with `GET /school-student/home` (SC-502). A 401 `school_session_expired` from any `request()` signs out and opens `/class?expired=1`. **Not yet:** the shared-device hint and the student variant of the Journey page (hide marketplace actions, quiz skip, regenerate) — M5 (SC-507).

### 6.3 QR badge `/class/badge`
- Uses the camera via the native `BarcodeDetector` (Chrome/ChromeOS/Android), falling back to **`jsqr`** (new dependency, approval needed) on other browsers. Needs the `Permissions-Policy` change in §0.
- `POST /school-login/badge {token}` → the same sign-in path as §6.1.
- *(as built — `pages/BadgeSignIn.tsx`)*: `/class/badge#<token>` signs in from the URL fragment (never sent to a server, removed from the address bar). The printed QR will encode that URL, so a phone or tablet camera app opens it directly — **no in-app scanner, no camera permission** needed, which drops `jsqr` and the `Permissions-Policy` change for now.

## 7. Documents (SC-301, SC-305, SC-307)

- **Uploader component**, used by the course wizard and the Documents page:
  1. Client-side checks: `.pdf` / `.docx`, ≤ 25 MB. `.doc` or `.docm` → "Open it in Word and *Save as* .docx or PDF".
  2. `POST /schools/{sid}/documents/upload-url` → `{document_id, upload_url, headers}`.
  3. `PUT` the file to `upload_url` with **`XMLHttpRequest`**, because `fetch` has no upload progress. Needs the CSP change in §0.
  4. `POST …/documents/{id}/complete`.
  5. Poll `GET …/documents/{id}` every 2 s until `ready | needs_ocr | failed`.
- Status chips: Uploading n % · Checking · Reading pages · Ready (n pages) · Needs a text version (`needs_ocr`: "This looks like a scan. Upload the original Word/PDF file, or [M3b] use text recognition") · Failed (with the reason from `document_rejected`).
- **Documents page (`/school/documents`)**: list with uploader, pages, used-by courses, delete. Deleting a document that a course cites shows a warning; the courses keep their content.
- Show a notice near the uploader: "Don't upload documents with students' personal information (marks sheets, reports)."

## 8. Course builder (SC-402..407, SC-410)

### 8.1 Create wizard (`/school/courses/new`)
1. **Material**: upload or pick 1–N ready documents.
2. **Course setup**: grade, subject, goal ("By the end, students can…"), length (number of steps or "about N lessons of M minutes"), language of instruction, "follow the document's order" (on by default).
3. **Estimate**: `POST …/courses/{jid}/estimate` shows approximate cost and time, plus the budget left. Continue → outline job.

### 8.2 Outline review
- Poll the job (`GET /schools/{sid}/jobs/{job_id}`) while showing "Reading your document…".
- An editable list of steps (title, description, type, minutes). Each step shows its **source sections with page numbers** (click → read-only preview of the chunk text).
- A "Not covered" panel lists `skipped_sections` with reasons. The teacher can turn any of them into a step.
- Reorder (up/down buttons; drag-and-drop is optional and needs no library), add, delete, rename.
- **Approve outline** → build job.

### 8.3 Build progress
- A progress bar from `job.progress` (`steps_done / steps_total`) and a per-step list with ✓ / spinner / "failed — retry". **Cancel** is available. Teachers can leave the page; the dashboard shows the running job.

### 8.4 Step editor (`/school/courses/:id`)
- Three panes (they stack on mobile):
  - **left:** step list with status (AI / Edited / Needs check ⚠).
  - **center:** markdown editor + live preview using `MarkdownContent` (same dialect as students see).
  - **right:** source panel with the cited chunks and page numbers, and **flags** from the critic ("This sentence isn't supported by the source").
- Actions per step: edit, **Regenerate with instructions** (text box; if the step was edited by a teacher, confirm "This replaces your edits" → `overwrite_teacher_edits=true`), "Make simpler", delete, move.
- Course meta: title, description, icon, tags.
- **Autosave** with `revision`. A 409 `draft_conflict` shows "Someone else changed this course — reload to see their changes", with a reload that keeps the user's unsaved text in a side panel for copying.
- **Preview as student** renders the draft in the student `Journey` layout, read-only, with a "Preview" banner.
- **Quiz preview** (optional): generates sample questions for a step without saving them.

### 8.5 Publish and versions
- **Publish** dialog: change summary (prefilled for v2+), a checklist (every step has content; open ⚠ flags count, which doesn't block but must be acknowledged), and "Publish to N assigned classes".
- **Versions** drawer: v1…vN with date, author and summary. **Restore** creates a new draft from that version (explain that publishing it makes it vN+1).
- Course list (`/school/courses`): status filter, "Mine / All school", duplicate, archive. Non-creator teachers see view, duplicate and assign only.

### 8.6 Update from a document (SC-601..606)
- Entry point: "Update from document" on a published course. Pick the mode (**Revise to a new edition**, **Add material**, **Rebuild**) and upload or pick documents.
- **Proposal review:** one card per proposal, with a side-by-side diff for `modify` (removed text red, added text green), the full step for `add`, the reason for `remove`. Accept or reject each, or accept all. Steps the teacher edited before carry a "Your edited step — suggestion only" label.
- Accepted proposals open in the editor as a new draft → publish as v(n+1).
- Student side: steps changed since the student completed them show an **"Updated"** badge on `StepNode`.

### 8.7 As-built backend contract (M4 SC-402..409) — authoritative

All routes are under `/api/v1/schools/{sid}` and need a staff member (any role).
Endpoints as shipped:

| Action | Endpoint |
|---|---|
| list / create course | `GET` / `POST /courses` |
| get course (+ draft) | `GET /courses/{jid}` |
| estimate cost | `POST /courses/{jid}/estimate` |
| generate outline | `POST /courses/{jid}/outline` (body = teacher inputs) |
| **approve outline → build** | `POST /courses/{jid}/build` (this *is* "approve outline"; `schoolApi.approveOutline` calls it) |
| regenerate one step | `POST /courses/{jid}/draft/steps/{step_id}/regenerate` `{instruction?, overwrite_teacher_edits?, expected_revision?}` |
| edit meta | `PATCH /courses/{jid}/draft` `{title?, description?, estimated_hours?, expected_revision?}` |
| add / reorder steps | `POST /courses/{jid}/draft/steps` · `POST /courses/{jid}/draft/steps/reorder` `{order:[step_id]}` |
| edit / delete step | `PATCH /courses/{jid}/draft/steps/{step_id}` · `DELETE …/{step_id}?revision=N` |
| hero image | `POST /courses/{jid}/hero-image` (school-billed; 503 `image_unavailable` until storage configured) |
| publish | `POST /courses/{jid}/publish` `{change_summary?, expected_revision?}` |
| versions / restore | `GET /courses/{jid}/versions` · `POST /courses/{jid}/versions/{version}/restore` |
| duplicate / archive | `POST /courses/{jid}/duplicate` · `POST /courses/{jid}/archive` |

- **Course shape** (`GET /courses/{jid}`): `{journey_id, title, status('draft'|'published'|'archived'), published_version, documents:[{id,filename,status,page_count}], draft}`. `draft` is `null` once published with no working draft (restore/duplicate makes a new one).
- **Draft shape**: `{version, revision, status, meta, steps}`. **`status` state machine** (from `meta.status`): `empty → outlining → outline_ready → building → built`; plus `outline_failed`, `build_failed`, and `published`. Poll the job (`GET /jobs/{job_id}` → `{status, progress:{steps_done,steps_total}, result}`) while `outlining`/`building`; the UI must treat those two as busy (edits return 409 `course_busy`).
- **Step shape** (draft): `{id, title, description, type, estimated_minutes, core_question, learning_objective, chunk_ids:[uuid], citations:[uuid], key_facts:[str], quiz_anchors:[{id,fact,chunk_ids}], body_md|null, flags:[{kind:'unsupported'|'build_error', claim?, reason?}], origin:'ai'|'teacher', edited_by_teacher:bool, build_status:'built'|'failed'|'empty'}`. Render `flags` as the right-pane "Check this" highlights; **never show `flags`/`citations`/`chunk_ids` to students** (publish strips them — the student journey carries only `id/title/description/type/estimated_minutes/core_question`).
- **Optimistic lock:** every mutating draft/publish call takes `expected_revision`; a stale value → 409 `{error:'draft_conflict', current_revision}`. Read it from `draft.revision`, resend it, and on conflict follow §8.4's reload-keeping-text flow.
- **Publish validation:** 409 `steps_incomplete` (`detail.steps` = step ids missing a body), `empty_course`, `course_busy`, `course_archived`. Regenerate adds 409 `teacher_edits_protected` (offer "replace my edits" → `overwrite_teacher_edits:true`) and `step_not_grounded` (teacher-authored steps have no source — edit by hand).
- Jobs (`build`, `outline`, `regenerate_step`) are async; reuse `usePollJob`. Cancel via `POST /jobs/{job_id}/cancel` (build/regenerate reset the draft to a rebuildable state).

## 9. Assignments and student home (SC-501..503, SC-507)

- Class → **Courses** tab: assign a **published** course, with an optional due date, tutor on/off and quiz required. Show each assignment's progress summary. Unassigning archives the assignment (progress is kept).
- **Student home (`/my-classes`)**: `GET /school-student/home` → for each class, cards for assigned courses with progress ring, due date ("Due Fri", red when overdue) and teacher name. Tap → `/journey/:id`.
- On `/journey/:id` for students: hide like/fork/share/marketplace actions and suggestions. Show the tutor only when the assignment allows it.
- 402 `school_budget_exhausted` → a friendly inline card: "Your class has used up its AI helpers for this month — tell your teacher". It never links to pricing.

## 10. Progress and analytics (SC-505, SC-701..707)

- Class → **Progress**: a matrix of students (rows) × assigned courses (columns). Cells show steps done/total with colour; overdue is outlined. Click → student drill-down.
- **Student drill-down**: per step completion, quiz attempts/score/hints and last active. Tutor transcripts appear when D4 allows, opened behind a "View conversation" click that is audited.
- "Needs attention" filter driven by the struggling flags.
- **Export CSV** button (the server escapes cells).
- **Usage (`/school/usage`, admins)**: monthly budget meter, spend by class and by course, and the per-student caps in effect.

## 11. ECALT admin — Schools tab (SC-111)

- In the existing admin page (`pages/admin/tabs/`): list schools (status, seats used/limit, budget used), create a school (name, country, seats, monthly budget), edit, suspend/terminate (typed confirmation), send the owner invite.
- *(as built)* `GET /admin/schools?q=&status=&limit=&offset=` → `{schools: [...], total}` (each with `staff_count`, `student_count`); `POST /admin/schools {name, country?, seat_limit?, monthly_ai_budget_cents?, owner_email?}` → 201 (includes `owner_invite` when `owner_email` was given); `GET/PATCH /admin/schools/{sid}` (`name`, `status`, `seat_limit`, `monthly_ai_budget_cents`); `POST /admin/schools/{sid}/owner-invite {email}`. Terminating is final (409 `school_terminated` on reopening).

## 12. Routes

| Path | Page | Who |
|---|---|---|
| `/school` | SchoolDashboard | staff |
| `/school/classes`, `/school/classes/:classId` | Classes, ClassDetail | staff |
| `/school/students` | Students (+ import wizard) | staff |
| `/school/courses`, `/school/courses/new`, `/school/courses/:id`, `/school/courses/:id/update` | Courses, CourseWizard, CourseEditor, CourseUpdate | staff |
| `/school/documents` | Documents | staff |
| `/school/staff`, `/school/settings`, `/school/usage` | Staff, SchoolSettings, SchoolUsage | admin |
| `/school/print/login-cards` | LoginCards (print layout) | staff |
| `/school-invite` | SchoolInviteAccept | invited staff |
| `/class`, `/class/badge` | ClassSignIn, BadgeSignIn | public |
| `/my-classes` | StudentHome | students |
| `/journey/:id` | Journey (existing, student variant) | students + everyone |

All of them are lazy routes in `App.tsx`, like the existing ones. Pages go in `pages/school/`; components in `components/school/` (`DocumentUploader`, `PicturePassword`, `StepEditor`, `SourcePanel`, `ProposalDiff`, `ProgressMatrix`, `LoginCard`).

## 13. `lib/schoolApi.ts`

Typed wrappers per README §3.15 group: `getMySchools`, `getSchool`/`updateSchool`/`acceptDpa`, staff (`listStaff`, `inviteStaff`, `updateStaff`, `removeStaff`, `acceptSchoolInvite`), students (`listStudents`, `createStudent`, `importStudents(dryRun)`, `updateStudent`, `resetStudentSecret`, `archiveStudent`, `restoreStudent`, `rotateBadge`, `deleteStudent`, `exportStudent`), classes (`listClasses`, `createClass`, `updateClass`, `deleteClass`, `addClassTeacher`, `enrollStudents`, `unenrollStudent`, `rotateClassCode`, `getLoginCards`), documents (`createUploadUrl`, `completeUpload`, `getDocument`, `listDocuments`, `deleteDocument`), courses (`listCourses`, `createCourse`, `estimateCourse`, `getCourse`, `getDraft`, `patchDraft`, `addStep`, `patchStep`, `deleteStep`, `reorderSteps`, `regenerateStep`, `approveOutline`, `publishCourse`, `listVersions`, `restoreVersion`, `duplicateCourse`, `archiveCourse`), updates (`startCourseUpdate`, `getProposals`, `decideProposal`, `acceptAllProposals`), jobs (`getJob`, `cancelJob`), assignments, analytics, usage, and the student calls (`lookupClass`, `classSignIn`, `badgeSignIn`, `getStudentHome`). Types go in `lib/types.ts` under a `// Schools` section.

A shared `usePollJob(jobId)` hook polls every 2 s with backoff up to 10 s and stops on a terminal status.

## 14. Error codes → UI

| Code | Status | UI |
|---|---|---|
| `school_role_required` | 403 | "Only school admins can do this" (hide the control next time via `can()`) |
| `school_access_suspended` | 403 | full-page notice (staff and students) |
| `school_student_not_allowed` | 403 | redirect student to `/my-classes` |
| `school_session_expired` | 401 | sign out → `/class` |
| `class_code_invalid` | 404 | inline on the code field |
| `invalid_student_secret` | 401 | shake + "try again" |
| `student_locked` | 423 | "Ask your teacher" + unlock time |
| `seat_limit_reached` | 409 | seat explanation |
| `dpa_required` | 409 | open the DPA modal |
| `document_rejected` | 422 | reason-specific message (§7) |
| `draft_conflict` | 409 | reload prompt keeping local text (§8.4) |
| `content_not_published` / `course_not_published` | 409 | "This course isn't published yet" |
| `content_locked` | 409 | hide "regenerate" on school courses (teachers edit in the builder) |
| `school_not_found` | 404 | "School not found" → back to `/school` picker |
| `parent_profile_required` (on `/schools/*`) | 403 | "Switch to your own profile to manage your school" |
| `invite_invalid` / `invite_expired` / `invite_email_mismatch` / `staff_must_be_adult` / `account_setup_required` | 404 / 410 / 403 / 403 / 409 | invite accept page (§3) |
| `last_owner` / `already_member` / `invalid_settings` / `dpa_version_mismatch` | 409 / 409 / 422 / 409 | inline on the staff, settings and DPA forms (§3) |
| `school_budget_exhausted` | 402 | student card (§9) / staff banner with usage link |

## 15. New dependencies (approval needed)

| Package | Why | Fallback without it |
|---|---|---|
| `qrcode` | QR badges on login cards (encode `<host>/class/badge#<token>`) | **current state:** cards ship without QR; badge sign-in works but has nothing to scan |
| `jsqr` | QR scanning where `BarcodeDetector` isn't available | not needed while badges open `/class/badge#…` from the device's camera app |
| `@playwright/test` (dev) | E2E smoke (D10) | manual QA checklist (`TESTING.md` §10) |

No editor library: the step editor is a `<textarea>` with the existing `MarkdownContent` preview. Reconsider a rich editor only if pilot teachers struggle with markdown.
