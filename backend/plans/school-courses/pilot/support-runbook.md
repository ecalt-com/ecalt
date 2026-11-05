# Schools support runbook (SC-806)

What to do when a school asks for help. Most requests are solved by the school's own admins in the product, so the first step is usually to show them where. ECALT staff use the **Admin → Schools** tab; we never sign in as a student and we don't read tutor chats.

**Who:** ECALT support (an account with `is_admin`). **Where it's recorded:** every action below lands in the school's audit log (`school_audit_log`).

## 1. Sign-in problems (students)

| Symptom | Cause | Fix (who) |
|---|---|---|
| "Wrong picture/PIN" for one student | Forgot their secret | School admin → Students → the key icon (**New sign-in**, also unlocks), or Class → **Print login cards** with new sign-ins (school) |
| Student is locked out (`423 student_locked`) | 5 wrong tries | Wait 15 min, or give them a **New sign-in** (school) |
| Whole class gets "too many attempts" at lesson start | Many sign-ins from one school network | Limits are per real IP (fixed in #19) and sized at 240/min per school network. If it recurs, raise `SCHOOL_SIGNIN_RATELIMIT` on Railway and note it in TRACKER |
| "Session expired" mid-lesson | Sessions end 12 h after sign-in (`SCHOOL_STUDENT_SESSION_HOURS`) | Sign in again — expected |
| Class code doesn't work | Code was regenerated, or class archived | Class page shows the current code (school) |
| QR badge stopped working | Badge reissued when cards were reprinted | Use the newest card (school) |
| Nobody can sign in (`503 login_unavailable`) | `FIREBASE_SERVICE_ACCOUNT_JSON` missing or broken on Railway | Ops: fix the variable, redeploy |

## 2. Staff problems

| Symptom | Fix |
|---|---|
| Invite link expired / lost | School admin → Staff → **Revoke** the old invite and invite the email again (links last 7 days). For the **first owner**: Admin → Schools → the school → *Invite owner* |
| Wrong role | School admin → Staff → change role |
| Teacher left | School admin → Staff → remove. Their courses stay with the school |
| Owner left, no admin remains | Admin → Schools → *Invite owner* with the new person's email |
| "Accept the data processing agreement" keeps appearing | `SCHOOL_DPA_VERSION` was bumped — an owner must accept the new text once |
| Staff sees "Switch to your own profile" | They're inside a family child profile — switch back to their own profile |

## 3. Courses

| Symptom | Fix |
|---|---|
| Wrong or unsupported sentence in a lesson | Teacher edits the step, or **Regenerate** with an instruction. The ⚠ "Check this" list shows what the fact-checker doubted |
| Teacher deleted/broke a published course | Course → **Versions** → *Restore* the last good version, then publish (becomes the next version) |
| Course stuck on "Reading your document…" / "Building…" | See §4 |
| Outline skipped a section the teacher wants | Outline review → *Not covered* → **Make a step** |
| Document "couldn't be read" | Scanned PDFs aren't supported (no OCR in the pilot). Ask for a Word file or a text PDF |
| Upload rejected as too large | Limit is `SCHOOL_DOC_MAX_MB` (25 MB). Split the file |
| AI features paused (`school_budget_exhausted`) | The month's AI budget is spent. Admin → Schools → raise the budget, or wait for the 1st. Admins got 80 % / 100 % emails |
| Students don't see a course | It must be **published** and **assigned** to their class (Class → Courses) |

## 4. Background jobs (stuck or failed)

Admin → Schools → **Background jobs**. It lists failed jobs (last 7 days) and stuck ones across all schools.

1. **Many jobs stuck in `queued`** → no worker is running. Check that exactly one Railway instance has `SCHOOL_JOBS_WORKER_ENABLED=true` and that it's healthy. The scheduler logs `school job queue stalled` every 15 min while this lasts (Sentry alert).
2. **One job failed** → read the error. Transient (provider timeout, rate limit): **Retry**. Repeats with the same error: open a bug with the job id; the teacher can keep working on other steps.
3. **A job runs forever** → **Cancel**. Build/regenerate jobs stop at the next step and leave the draft rebuildable; the teacher can approve the outline again.
4. Stale `running` rows from a redeploy are re-queued automatically after `SCHOOL_JOBS_STALE_LOCK_MINUTES`.

## 5. Data requests

| Request | Fix |
|---|---|
| Parent asks for a child's data | The school is the controller: school admin → Students → the student → **Export**. Pass the request to the school if it came to us |
| Delete one student | School admin → Students → **Delete** (account, progress, chats and sign-in are erased; a pseudonymised consent record stays) |
| End of year | School admin archives students (no sign-in, data kept) or deletes them |
| Teacher wants to see a student's tutor chat | Class teachers and school admins can, from the progress drill-down; every view is audited. The school can switch this off in Settings |

## 6. Suspending or ending a school

- **Suspend** (non-payment, investigation): Admin → Schools → status `suspended`. Everyone loses access at once; data is kept; set back to `active` to restore.
- **Terminate** (contract ended): status `terminated` (type the name to confirm). Access stops now; the admin tab shows the deletion date; the nightly job deletes everything 30 days later (runbook `rollout-runbook.md` §5a). Remind the school to export first.
- **Early deletion** requested in writing: `python scripts/purge_school.py <school_id> --delete --ignore-grace` (ops), then confirm in writing (DPA 9.3).

## 7. Incidents

- **Possible data exposure** (a school sees another school's data, a student sees staff screens): suspend the affected school(s), page engineering, preserve logs. The DPA requires notifying the school without undue delay (`legal/dpa-template.md`).
- **Bad release**: roll back the Railway deployment (`rollout-runbook.md` §5).
- **AI provider down**: course building and the tutor fail; jobs retry with backoff. Nothing to do but tell schools; retry failed jobs afterwards.

## 8. Useful checks (ops)

- Health: `GET /api/v1/health`.
- Rate-limit keying: `GET /api/v1/admin/diagnostics/client-ip` (admin) — `limiter_key` must be your own IP.
- What's left of a terminated school: `python scripts/purge_school.py <school_id>`.
- Job queue: Admin → Schools → Background jobs, or `GET /api/v1/admin/schools/jobs?state=attention`.
