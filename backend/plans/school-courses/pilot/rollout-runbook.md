# Schools go-live runbook (SC-807, #10)

How to switch the schools feature on in **production** — first for one pilot school, later for everyone — and how to switch it off again. The code is already in prod (PR #6) and dormant: with `SCHOOLS_ENABLED` unset, every `/schools`, `/school-invites`, `/school-login`, `/school-student` and `/admin/schools` route returns 404.

**Who runs it:** a person with Railway + Supabase prod access. Railway env changes are a manual ops step (never automated).

## 1. Gates — do not start until all are ticked

| Gate | Issue | Status (2026-10-25) |
|---|---|---|
| Legal: counsel-approved terms, DPA, privacy notice; DPA text in app + `SCHOOL_DPA_VERSION` bumped | #7 | 🟨 drafts ready, awaiting counsel |
| Security review | #8 | ✅ done (`SECURITY-REVIEW.md`) |
| Pilot school recruited | #9 | ⬜ kit ready (`pilot-kit.md`) |
| Offboarding deletion job (DPA promises it) | #17 / SC-803 | ⬜ |
| Sentry scrubbing + no analytics on student sessions | memo G4/G5 | ⬜ |
| Prod AI config rows for school interaction types | #18 | ⬜ (code defaults work meanwhile) |
| Rate-limit keying verified behind Railway's proxy | #19 | ⬜ |
| CSP `'unsafe-inline'` removed | #25 | ✅ done 2026-10-26 (reaches prod with the `master` merge) |

## 2. Preflight (prod, read-only checks)

- [ ] **Migrations** 014–017 applied to the prod database (`SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 5`, or check `school_usage.alert_80_at` exists).
- [ ] **Storage bucket** `school-materials` exists in prod Supabase, **private**, with a file size limit = `SCHOOL_DOC_MAX_MB` (25 MB).
- [ ] **Railway variables** present on the prod `ecalt-api` service (verify names exist; don't paste values anywhere):
  - `FIREBASE_SERVICE_ACCOUNT_JSON` — student sign-in mints custom tokens (503 `login_unavailable` without it)
  - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — document storage (503 without them)
  - `SCHOOL_JOBS_WORKER_ENABLED=true` on **exactly one** instance — runs extract/outline/build/update jobs
  - `SCHEDULER_ENABLED=true` (prod only) — teacher digest, audit-log pruning
  - `SENTRY_DSN` with scrubbing configured (G4)
  - Optional overrides: `SCHOOL_DPA_VERSION` (must match the counsel text), `SCHOOL_DOC_MAX_MB`, `SCHOOL_STUDENT_SESSION_HOURS`
- [ ] **Firebase** prod project allows custom-token sign-in (service account has the Token Creator role).
- [ ] **Frontend**: `master` deployed on Vercel includes the schools UI (it does since PR #6); CSP `connect-src` covers Supabase storage uploads (`*.supabase.co`).
- [ ] `feature/dev` merged to `master` with everything since PR #6 (M6 finish, security fixes, profiling fix) — **the security fixes must be in prod before the flag flips.**

## 3. Switch on — pilot

1. Railway → prod `ecalt-api` → Variables → set `SCHOOLS_ENABLED=true` → deploy restarts.
2. Health: `GET https://ecalt-production.up.railway.app/api/v1/health` → `ok`.
3. Smoke (as the ECALT admin in prod):
   - [ ] `/admin` → Schools tab loads (not the "SCHOOLS_ENABLED is off" notice).
   - [ ] Create the pilot school (seat limit, monthly AI budget); send the owner invite.
4. With the school owner (screen-share):
   - [ ] Owner accepts the invite → accepts the DPA (correct version shown).
   - [ ] Create one class + **one test student** → print a login card → sign in on a school device with the class code + picture password → lands on `/my-classes`.
   - [ ] Upload a short document → extraction reaches `ready` (job worker is running).
   - [ ] Build a 2-step course → publish → assign to the class → the test student sees it, opens a step, asks the tutor one question.
   - [ ] Teacher sees the student in the progress matrix.
   - [ ] Delete the test student (cascade works).
5. Hand over: real classes + students only after this passes.

**Other schools stay invisible**: nothing is listed publicly; a school exists only once an ECALT admin creates it. The flag is global, so "pilot" means "only the pilot school has been created".

## 4. Watch (first two weeks)

| What | Where | Act when |
|---|---|---|
| Job failures (extract / outline / build / update) | `school_jobs` where `status='failed'`; Railway logs | any repeat failure for the same school |
| 5xx on school routes | Railway logs / Sentry (tag `school_id`) | any |
| Sign-in lockouts (`423 student_locked`) and throttling | logs | spikes at lesson start → check #19 keying |
| AI spend vs budget | `/school/usage`; 80 %/100 % alert emails | 80 % within the first half of the month |
| Teacher-reported content problems | feedback calls | any unsupported claim reaching students |

## 5. Switch off (rollback)

- **Whole feature:** unset `SCHOOLS_ENABLED` (or `false`) → redeploy. All school routes (staff, admin, student sign-in, student home) 404 at once; data stays in the database untouched. ⚠️ Students **already signed in** can still open their assigned courses (journey/progress/quiz/tutor routes aren't behind the flag) until their 12-hour session ends — to cut them off immediately, also suspend the school. Switch back on to resume.
- **One school:** ECALT admin → Schools → set the school `suspended` (staff and students get 403 `school_access_suspended`; data kept) or `terminated` (starts the 30-day deletion once SC-803 ships).
- **Bad release:** redeploy the previous Railway deployment; migrations are additive, so the old code runs on the new schema.

## 6. GA (after the pilot)

- [ ] Pilot success measures met (`pilot-kit.md` §6) and feedback addressed.
- [x] CSP tightened (#25).
- [ ] Load tests (#17 / SC-802), support runbook (SC-806).
- [ ] Microsoft staff sign-in (D8) — Firebase `microsoft.com` provider + a button on the staff sign-in; many schools use Microsoft 365. **Not built yet.**
- [ ] Decide self-serve vs sales-led onboarding (D2).

## 7. Record

Log each step (date, who, result) in `TRACKER.md` → Changelog, and close #10 after the pilot school's first real class is live.
