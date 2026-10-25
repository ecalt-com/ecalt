# SC-801 — Schools pre-launch security review

**Date:** 2026-10-25 · **Issue:** ecalt-com/ecalt#8 · **Scope:** every `/schools/{id}/…`, `/school-login/*`, `/school-student/*`, `/admin/schools/*` route, the student allowlist, document upload/extraction, the AI course builder + update pipeline, the student journey renderer, and frontend dependencies.

**Verdict:** one high-severity issue (stored XSS from teacher content to students) and four lower ones were found and **fixed**. The authorization matrix and tenant isolation held up. Remaining items are listed under *Residual risk* — none blocks a supervised pilot, but the CSP item should be done before GA.

## Method

| Area | How |
|---|---|
| Authorization matrix | Reviewed `tests/integration/schools/authz_matrix.py` against the code (one row per route × 12 personas, AUTHZ-COV fails CI on a missing row) and against decision D4 |
| IDOR / tenant isolation | Extended the ISO sweep to M6 (update, proposals, apply, decide) and M7 (progress, drill-down, CSV, transcripts), including school-B ids smuggled in request **bodies**; a digest asserts school B is untouched |
| Malformed input | New fuzz: every school route with a path parameter × 4 garbage values (non-uuid, SQL-ish, near-uuid, NUL byte) → must be 4xx |
| Student surface | Read `STUDENT_ALLOWED_ROUTES`; checked id-keyed routes outside the journey sweep (`/quiz/{quiz_id}/hint`, `/submit` — owner-filtered, OK) |
| Upload pipeline | Read `school_document_service`, `school_storage_service`, `school_ingest_service`, `doc_parsing`, the sandboxed extract worker |
| Prompt injection / output | Read the builder sanitizer + content filter and every path that writes AI or document text into a course (build, regenerate, update modify/add, replace) |
| Renderer | Traced step content to `MarkdownContent` → `SvgDiagram` (`dangerouslySetInnerHTML`) and checked the CSP in `frontend/vercel.json` |
| Sessions / lockout | Existing SEC-03..07 coverage (lockout, class-code throttle keyed on code+student, uniform errors, badge rotation, 12 h session) — reviewed, unchanged |
| Dependencies | `npm audit --omit=dev` on the `feature/dev` lockfile + open Dependabot alerts |

## Findings

| # | Severity | Finding | Fix |
|---|---|---|---|
| F1 | **High** | **Stored XSS, teacher → students.** `MarkdownContent` injects an inline `<svg>` block with `dangerouslySetInnerHTML`. AI-written school bodies are stripped of HTML, but teacher edits (`PATCH …/draft/steps/{id}`, `POST …/draft/steps`) stored `body_md` verbatim and publish copied it into the student-facing `step_content`. `<svg><image href=x onerror=…></svg>` would run in a child's browser — the CSP allows `'unsafe-inline'` scripts, so inline handlers execute. | `school_course_service._safe_body`: scripts removed and any SVG must pass the same allowlist as AI diagrams (`ai_service.sanitize_step_diagrams`) — applied on step edit, on step add, and again on every publish (covers restored versions and anything stored earlier). Frontend defense in depth: `SvgDiagram` refuses SVG that fails a mirror of the allowlist. |
| F2 | Medium | **Transcripts visible to any teacher in the school.** D4 is "teachers see transcripts for their own classes"; the routes used class *read* access, so a teacher of another class could read a child's tutor conversations. | `list_student_transcripts` / `read_student_transcript` now `load_class(..., manage=True)` → class teachers + school admins; others 403 `school_role_required` (no audit row written). Matrix rows updated (T2 → `role`). The drill-down UI already hides the section on any error. |
| F3 | Low | **Unverified bytes parsed after upload (TOCTOU) + unbounded download.** The signed upload URL allows overwrites; `complete` verified the file and stored its sha256, but extraction downloaded the object again without checking it, and `download()` read any size into API memory. | Extraction refuses bytes whose sha256 differs from the verified one (`changed_after_upload`); `storage.download(max_bytes=…)` streams and aborts past the limit (used by both `complete` and extraction). |
| F4 | Low | **Untrusted document headings → step titles.** In the update path an "add" step's title came straight from the uploaded document's heading, skipping the sanitizer (invariant I9). React escapes it, so not XSS, but HTML/links could reach a published title. | Titles go through `_sanitize_md` (fallback "New section"). |
| F5 | Low | **500s and error leakage.** A malformed `conversation_id` hit a uuid cast (500); a NUL byte in any text path/body param raised in psycopg2 (500 app-wide); and the generic DB 500 echoed the exception text (SQL / constraint names) to the client. | `uuid_or_404` on the conversation id; `get_db` maps NUL-byte input to 400 `invalid_input` and returns a generic "Internal server error" (details stay in the log). |
| D1 | Critical→none (prod deps) | `npm audit`: dompurify (critical, via mermaid), react-router-dom open-redirect→XSS, mermaid, katex, protobufjs. | `npm audit fix` (no breaking changes): dompurify 3.4.17, mermaid 11.17.2, react-router-dom 6.30.6. Build green. |

No cross-tenant access was found: every M6/M7 call with school-B objects returned 404 and left school B's rows unchanged.

## Tests added

`tests/integration/schools/test_security_review.py` (65 cases): ISO sweep for M6/M7 + body-borne ids; malformed-id fuzz across every parameterised school route; XSS on edit / add / publish (safe diagram kept); D4 transcript scoping + malformed conversation id; swapped-after-verification and oversized uploads; sanitized headings in update proposals. `authz_matrix.py` transcript rows now expect T2 → 403.

## Residual risk / follow-ups

| Item | Why it matters | Owner / when |
|---|---|---|
| **CSP `script-src 'unsafe-inline'`** | It's what made F1 exploitable. Removing it (Vite emits no inline scripts; check Firebase/Stripe/Razorpay loaders) turns any future HTML-injection bug into a non-event. | ✅ Done 2026-10-26 (#25): removed, plus `object-src 'none'` and `base-uri 'self'`; `e2e/csp.authed.spec.ts` |
| SEC-08 rate-limit keying | slowapi keys on remote IP; a school behind one NAT shares limits. | #19 |
| SEC-15 admin impersonation of a student | Not covered by a test yet (staff routes resolve the admin's own uid, so they 404, but it's unasserted). | Next security pass |
| Class progress / drill-down visible to every staff member | Design choice (D4 only covers transcripts). Confirm with the pilot school; tighten like transcripts if wanted. | Product decision |
| Supabase bucket size limit | Set a bucket `file_size_limit` = `SCHOOL_DOC_MAX_MB` so storage itself refuses oversized objects. | Ops (dashboard) |
| firebase → @grpc/grpc-js (high, npm) | Only in the Firestore package; the app uses Firebase Auth only, and npm's "fix" is a downgrade to firebase 9. Accepted. | Re-check on the next firebase release |
| react-router backslash open redirect (moderate) | Fixed only in v7. The app never navigates to a user-supplied path, so it isn't reachable. Accepted until a v7 upgrade. | — |
| Dependabot alerts on `master` | Most (incl. `next`, `sharp`, `vite`, `postcss`) are from master's older lockfile; they clear when `feature/dev` merges. | Next merge |
