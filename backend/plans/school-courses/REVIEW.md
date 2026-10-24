# Schools feature — code review & bug report

_Reviewed 2026-10-12 against `feature/dev` @ `0c1a56e`. Scope: everything shipped in M0–M2 (tenants, staff, invites, students, classes, login cards, student sign-in). M3+ (document ingestion, course builder, assignments, analytics) is not built yet and is out of scope except where M2 depends on it._

## Verdict

The feature is **well-architected and unusually careful** for a v1 — tenant isolation is enforced in both the schema and the code, the student blast-radius is tightly contained, secrets are handled correctly, and almost every path fails closed. It is safe to demo and to pilot with **test** schools.

There is **one functional blocker** that will bite the first real classroom (students can't actually use the AI tutor/quiz past a handful of messages — see H1), a few **medium** hardening gaps around sign-in abuse and the audit log, and a short list of polish items. None of the medium/low items should block a gated pilot, but H1 and the legal sign-off (SC-002) should be closed before a real class touches it.

Severity key: **H** = fix before a real class uses it · **M** = fix during the pilot · **L** = polish / defense-in-depth.

---

## What's done well (keep it)

- **Tenant isolation is belt-and-suspenders.** Every child table carries `school_id` and references its parent through composite `(id, school_id)` foreign keys (`migrations/014_schools.sql`), so a row physically cannot join a class/student/course from another school. Every service query also filters `ctx.school_id`. A school you don't belong to is a **404, not a 403**, so existence never leaks (`core/school_auth.py:resolve_school_ctx`).
- **The student blast-radius is tightly contained.** School students (`stu_` uids) are confined to an explicit route allowlist enforced at the *root* auth dependency (`get_signed_in_uid` → `enforce_student_route`), matched by **endpoint function, not path**, and it **fails closed** — a route added later is denied to students until deliberately allowlisted. `tests/api/schools/test_student_allowlist.py` enumerates routes to keep the list honest.
- **Journey access is gated everywhere.** `assert_can_read_journey()` is called on every journey-id endpoint across `journeys.py`, `quiz.py`, `chat.py`, `progress.py`, and every pool-building query (`lists`, `sitemap`, recommendations, scheduler scans, admin stats, marketplace) filters `school_id IS NULL`. This is the kind of thing that's easy to miss in one place and leak a school course into the marketplace — it looks complete here.
- **Secrets are handled correctly.** scrypt-hashed, returned exactly once, picture indices stored as numbers (frontend ordering is load-bearing and documented as "never reorder"), QR badge stored as sha256. Sign-in uses a timing equaliser (`_equalise_timing`) so a missing roll number doesn't respond faster than a wrong secret.
- **Abuse controls don't key on IP** — correct, because a whole school NATs to one address (R7). Per-student lockout (5 → 15 min) and a per-class throttle (50 failures / 10 min) instead.
- **Compliance scaffolding is present:** DPA gate before any student is created (`_require_dpa`), `consent_events` `school_authorization` row per student, `school_audit_log` written in the same transaction as every mutation, last-owner protection with row locks against concurrent demotion.
- **Caches fail closed** (membership, account status, journey access all reject rather than guess on a DB error) and are invalidated on the right events.

---

## Bugs & correctness issues

### H1 — School students inherit the `free_trial` plan, so the tutor and quizzes stop working after ~6 messages

**Files:** `services/subscription_service.py:10` (`get_user_plan`), `:139` (`check_budget`); consumed by `endpoints/chat.py:39` and `endpoints/quiz.py:50`.

A school student is a `users` row with no subscription and no family link, so `get_user_plan()` falls through its `COALESCE(...)` to **`'free_trial'`**. The student-allowlisted AI routes then hit the individual budget gate:

- **In-course tutor** (`chat.py`, `context="chat"`): free-trial path caps at `lifetime_message_limit` (**default 6 messages, ever**) → `402 free_trial_exhausted`.
- **Quizzes** (`quiz.py`, `context="ai"`): free-trial token budget (`token_budget_cents`, **default ~20¢ lifetime**) → `402 budget_exhausted`.

Meanwhile the school-level controls that are supposed to govern this — `schools.monthly_ai_budget_cents`, and the `SchoolSettings.student_daily_tutor_messages` / `student_daily_quiz_sets` fields — are **set, stored, and exposed in the admin UI but never read by any code path**, and `school_usage` is **never written to**. They are dead config until **SC-504 (M5, not started)**.

**Impact:** The student AI experience shipped in M2 is effectively non-functional — a child gets ~6 tutor turns total before being told to upgrade (with an upgrade URL they can't use). This is the single thing most likely to go wrong in front of a real class.

**Why it's subtle:** SC-504 is correctly scheduled for M5, so "school budgets" aren't *missing* — but M2 put students on the tutor/quiz allowlist *before* the budget that governs them exists, and the fallback is the individual free trial rather than "unlimited" or "school-funded." The tracker doesn't call out this interaction.

**Recommended fix (interim, before a real class):** make budget resolution school-aware for `stu_` uids — the smallest version is to special-case `get_user_plan`/`check_budget`/`record_usage` so a student's spend is checked and recorded against their school (`schools.monthly_ai_budget_cents` + `school_usage`) with the per-student daily caps from settings, returning `402 school_budget_exhausted`. That is exactly SC-504; pulling its tutor/quiz slice forward (even a simplified "school has a working allowance, students aren't on free_trial") is the real unblock. At absolute minimum, confirm the intended behaviour before onboarding — today it silently blocks.

---

### M1 — No coarse rate limit on `POST /school-login/sessions` or `/badge`

**File:** `endpoints/school_login.py`.

Only the GET `classes/{code}` lookup has a limiter (`120/minute`, keyed by code). The two POST sign-in endpoints have **no slowapi limit at all** and rely entirely on the DB throttles. That's a deliberate design (don't key primary limits on a shared-school IP), but there's no backstop:

- Every `/sessions` attempt — even for a nonexistent student — runs an intentionally **CPU-expensive scrypt verify** (`_equalise_timing`) and writes an audit row before the per-class throttle (50/10 min) trips. A distributed sprayer hitting many valid class codes can drive real CPU/DB load.
- `/badge` has **no per-badge and no per-class throttle** — only the 192-bit token entropy and a 50 ms sleep on failure. Brute-forcing a token is infeasible, but there's nothing bounding request volume.

**Fix:** add a generous IP-or-global backstop limit to both POST endpoints (e.g. a few hundred/min) purely as a flood guard. It doesn't replace the keyed limits; it caps the pathological case. (Related: SC-009 is already tracking the proxy-IP keying question for `get_remote_address` behind Railway — resolve that first so the backstop isn't platform-wide.)

---

### M2 — `school_audit_log` is both the throttle counter and an unbounded, unpruned table

**Files:** `migrations/014_schools.sql:330` (table, no FK, no retention), `services/school_login_service.py:142` (throttle `COUNT` on every attempt).

The class throttle runs `SELECT COUNT(*) FROM school_audit_log WHERE school_id=… AND action='student.sign_in_failed' AND target_id=… AND created_at > now()-interval` on **every** sign-in attempt. The table is append-only, has no FK (deliberately — it outlives a deleted school), and **nothing prunes it**. Over a pilot it grows without bound, every failed-login writes a row, and the throttle query scans the school's rows in the window.

**Fix:** (a) add a retention/pruning job (or monthly partitioning) for `school_audit_log`; (b) consider a dedicated lightweight counter (e.g. a small `(school_id, class_id, window)` tally or a cache) for the throttle rather than scanning the audit log on the hot path. The existing `school_audit_log_school_idx (school_id, created_at DESC)` helps but the predicate also filters `action`/`target_id`.

---

### M3 — Picture-password entropy is low (16³ = 4096); it's only safe because the lockouts hold

**Files:** `services/school_student_service.py:49` (`generate_secret`), `:58` (`canonical_secret`).

Picture passwords are 3 picks from 16 icons, order significant, **repetition allowed** → 4096 combinations. That's fine *given* the per-student lockout (5/15 min) and class throttle, which bound online guessing to ~480 attempts/student/day with the class tripping first. But 4096 is thin defense-in-depth: if a lockout path ever regresses, the space falls in minutes.

**Notes/fix:** picture secrets are defaulted to grade ≤ 4 (D1), but `secret_kind` can be overridden on create/import for any grade, so a 10th-grader could end up with a 4096-space secret. Consider (a) forbidding `picture` above the grade threshold rather than only defaulting, and/or (b) raising to 4 picks or 20 icons for a meaningful bump. Low urgency while lockouts are intact.

---

### M4 — Successful sign-in is audited and the lockout cleared *before* the token is minted

**File:** `services/school_login_service.py:176-209`.

On success, `failed_attempts`/`locked_until` are reset and a `student.signed_in` audit row is written **inside** the transaction, which commits when the `with get_db()` block exits. `_custom_token()` (which can raise `503 login_unavailable` if the Firebase key is missing/unparseable) runs **after** the commit (`:206`). So a key problem produces an audit trail that says the student signed in, and a cleared lockout, while the student actually got a 503.

**Fix:** mint the token before the final commit (or audit mint failures). Minor — telemetry/integrity only, not a security issue — but it muddies exactly the signal you'd look at when diagnosing a login outage like the one we just fixed.

---

## Lower-severity / polish

- **L1 — `FIREBASE_SERVICE_ACCOUNT_JSON` is re-parsed on every mint.** `firebase_admin.py:120` `mint_custom_token` calls `json.loads(...)` each time (the OAuth *access* token is cached, but the service-account JSON parse isn't). Parse once at module load / cache the parsed dict and the loaded private key.
- **L2 — Badge tokens churn but can't be printed yet.** `login_cards(reset=True)` (the default, and the "whole class" button) rotates every student's `badge_token_hash`, but the printed card renders no QR (the `qrcode` dep isn't approved — SC-206/§15). So each reset silently invalidates any previously-issued badge while no usable badge is produced. Consider not rotating the badge until QR printing ships, or decoupling badge issuance from secret reset.
- **L3 — Roster lookup leaks `secret_kind`.** `lookup_class` returns each student's `secret_kind` (picture vs pin) to anyone with the class code when `login_roster_visible` is on (accepted risk R12). It's needed to render the right pad, but it also tells an attacker which secret to attempt. Minor; acceptable given the throttles.
- **L4 — Wrong secret *kind* burns a lockout attempt.** `school_login_service.py:175` requires `student["secret_kind"] == secret_kind` to even attempt verification; a mismatch falls through to the failure branch and increments `failed_attempts`. With a hidden roster (student toggles picture/PIN themselves) a child who picks the wrong mode loses an attempt instead of getting a "that's the other kind" hint. UX only.
- **L5 — Deleting a student who never signed in logs a warning.** `delete_student` → `purge_login("stu_…")` → `delete_firebase_user` 400s (no Firebase record exists until first `signInWithCustomToken`) and logs a warning. Benign but noisy; consider treating "user not found" as success.
- **L6 — Migration runner points at a nonexistent dir.** Not school-specific, but it affects applying `014`: `scripts/run_migrations.py` sets `MIGRATIONS_DIR = backend/migrations` which doesn't exist (migrations live at repo-root `../migrations`). Worth a one-line fix so `run_migrations.py` is usable instead of hand-applying via MCP.
- **L7 — `SchoolSettings` validation is silently forgiving.** `effective_settings` catches a `ValidationError` on stored settings and falls back to all-defaults with a log line. Correct for forward-compat, but a corrupted settings blob would quietly reset *every* setting (including `login_roster_visible`) to default rather than failing loudly. Low risk; note it.

---

## Operational / rollout gaps (not code bugs)

- **SC-002 legal sign-off** (school terms, DPA template, privacy notice, pilot-jurisdiction memo) is the stated go-live blocker for real student data. Code enforces `dpa_required`, but the DPA *text/version* (`SCHOOL_DPA_VERSION = '2026-10'`) is a placeholder until legal lands.
- **SC-207 live custom-token check** — now unblocked (the Firebase key is set on dev and prod). The remaining verification is a real end-to-end `signInWithCustomToken` against each project and confirming the Firebase Auth plan's limits for custom-token users (**R16 — MAU/Identity-Platform pricing** if many students sign in).
- **Dev Railway service isn't GitHub-connected** — it only updates on `railway up`, so `feature/dev` can silently drift from what's deployed on dev.
- **Key hygiene** — the two downloaded Firebase admin keys in `~/Downloads` should be deleted (Railway holds its own copies), and the Supabase service-role key in `.claude/settings.local.json` should be removed and rotated.

---

## Testing gaps

The `schools_db` suite (727 green) covers the DB-backed authz matrix and flows well. Worth adding:

1. **A budget test for `stu_` uids** that asserts the *intended* behaviour (this would have caught H1): a student's Nth tutor message / quiz either succeeds under a school allowance or fails with `school_budget_exhausted` — not `free_trial_exhausted`.
2. **A sign-in flood test** asserting the class throttle trips and that a coarse backstop (M1) exists.
3. **A login-card reset test** proving `reset=false` leaves existing secrets untouched and only fills in the missing ones (guards the sharp "whole class" default).
4. **An end-to-end custom-token test on dev** (SC-207) — the one thing unit tests can't cover because it needs a real Firebase project.

---

## Suggested priority order

1. **H1** — make student AI budget school-aware (or consciously decide the interim), *before* a real class. This is the headline.
2. **SC-002** legal sign-off + real DPA text/version.
3. **SC-207** live `signInWithCustomToken` check on dev and prod; confirm Firebase pricing (R16).
4. **M2** audit-log retention + throttle counter; **M1** sign-in flood backstop (after SC-009).
5. **M4 / M3 / L-items** as polish during the pilot.

---

## Resolution — implemented 2026-10-12

All bug/hardening items below were implemented and tested (schools suite 734 green; default suite at the 62-failure baseline, no new breakage; frontend `npm run build` clean). The "what would make it better" enhancements (full SC-504, analytics, doc ingestion) remain future milestones.

| Item | Status | What changed |
|---|---|---|
| **H1** student budget | ✅ Fixed | `subscription_service`: students resolve to a **school-funded** budget, not free_trial. `check_budget` blocks with `school_budget_exhausted` when the school's `monthly_ai_budget_cents` is 0 or the monthly pool (read from `school_usage`) is spent, and `school_daily_limit_reached` on the per-student daily caps. `record_usage` now writes `school_usage` and the per-student daily counters. `budget_error_detail()` gives students a friendly 402 (no upgrade link); chat/quiz endpoints use it. Frontend: `UpgradePrompt`/`QuizCard` show a no-upsell message for the school codes. |
| **M1** sign-in flood | ✅ Fixed | IP backstop limits on `POST /school-login/sessions` and `/badge` (`SCHOOL_SIGNIN_RATELIMIT` / `SCHOOL_BADGE_RATELIMIT`, tunable; sized for a bell-time burst; comment flags the SC-009 proxy-IP dependency). The DB throttles remain the primary defence. |
| **M2** audit log growth | ✅ Fixed | Partial index `school_audit_log_signin_fail_idx` for the throttle count + a daily scheduler job `prune_school_audit_log` that drops `student.sign_in_failed` rows older than `SCHOOL_SIGNIN_FAIL_RETENTION_DAYS` (default 30), keeping all other audit events. |
| **M3** picture entropy | ✅ Partly | Picture passwords are now **rejected** (not just defaulted away) above grade `PICTURE_MAX_GRADE` (4) on create/reset, and coerced to PIN in CSV import. Raising the length/alphabet (4096→more) is deferred — it would break existing cards and the frontend pad, and the lockouts hold. |
| **M4** mint-before-commit | ✅ Fixed | The Firebase custom token is minted **inside** the sign-in transaction (both class-code and badge), so a mint failure rolls back the lockout reset and the `signed_in` audit — no phantom "signed in" record. |
| **L1** JSON re-parse | ✅ Fixed | `firebase_admin._service_account()` caches the parsed key per raw value and returns `None` on malformed JSON (→ 503, never 500). |
| **L2** badge churn | ✅ Fixed | `login_cards` issues a badge only when the student has none; a secret reset no longer rotates an existing badge (reprint can't show it until QR ships, and badge sign-in is live). `rotate_badge` stays the explicit roll. |
| **L4** wrong-kind lockout | ✅ Fixed | A well-formed secret of the wrong kind (picture vs PIN) returns the generic error without burning a lockout attempt. |
| **L5** delete noise | ✅ Fixed | `delete_firebase_user` treats `USER_NOT_FOUND` as success (student who never signed in). |
| **L6** migration runner | ✅ Fixed | `scripts/run_migrations.py` now points at the repo-root `../migrations`. |
| **L7** settings salvage | ✅ Fixed | `effective_settings` salvages valid fields instead of resetting all settings when one stored value is invalid. |
| **L3** roster `secret_kind` leak | ⏭️ Kept | Needed to render the right pad; accepted risk (R12), bounded by the throttles. |

Migration: `migrations/015_schools_budget_and_login_hardening.sql` (daily-usage counters + throttle index). Apply to dev and prod before the backend deploys. New settings: `SCHOOL_SIGNIN_RATELIMIT`, `SCHOOL_BADGE_RATELIMIT`, `SCHOOL_SIGNIN_FAIL_RETENTION_DAYS`.

Tests added: `tests/integration/schools/test_student_budget.py` (H1), plus wrong-kind-no-lockout (L4) and login-card badge decoupling (L2) cases.

---

## What would make the feature genuinely better (beyond fixes)

- **A working school budget + per-student daily caps with admin visibility** (SC-504 + SC-706) is the biggest value-add — it turns `monthly_ai_budget_cents` from decoration into the cost-control story that makes the feature sellable, and it unblocks H1.
- **Teacher-facing "who's stuck" analytics** (SC-701+): the data (progress, quiz results) is already captured per student; surfacing per-class/per-course completion and struggling-student signals is what teachers will actually log in for.
- **A dry-run-first, estimate-before-you-spend document→course flow** (M3/SC-402) with explicit cost estimates — matches the careful tone of the rest of the feature and pre-empts the "AI cost overrun" risk (R9).
- **Bulk login-card UX**: a single "print what's missing" default (rather than reset-all) plus optional QR once the dep lands would make start-of-term far less error-prone.
- **A "class mode" session** (short, auto-expiring, device-bound) is already half-built via `auth_time` + session persistence; making the shared-device sign-out prominent and the expiry visible to the child would close R8 cleanly.
