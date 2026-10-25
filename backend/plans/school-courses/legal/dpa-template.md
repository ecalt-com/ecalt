# Data Processing Agreement — ECALT for Schools

> **DRAFT for counsel review — not legal advice.** Version `[2026-10]` (must match `SCHOOL_DPA_VERSION`; bump it whenever this text changes so school owners accept again). `[ ]` marks blanks. See `compliance-memo.md` for the reasoning and open questions.

This Data Processing Agreement ("**DPA**") is between **[School legal name]** ("**School**") and **[ECALT legal entity]**, [address] ("**ECALT**"), and forms part of the ECALT for Schools Terms (the "**Terms**"). It is accepted in the product by the School's owner account; acceptance is recorded with the version, the person and the time.

## 1. Roles

1.1 The School is the controller (under the Digital Personal Data Protection Act, 2023: the **Data Fiduciary**) of all personal data of its students and staff processed in the service ("**School Data**"). ECALT is the processor (**Data Processor**).

1.2 ECALT processes School Data only on the School's documented instructions. The Terms, this DPA and the School's use of the product's settings (for example adding students, assigning courses, turning teacher transcript access on or off) are the School's instructions. If ECALT believes an instruction breaks the law, it will tell the School.

1.3 The School confirms it has the legal authority to provide School Data and to authorise processing for students under 18, including any notice to parents its rules require. ECALT provides a template notice (Annex D) for the School to use.

## 2. Scope of processing

The subject matter, purpose, data categories and data subjects are in **Annex A**. ECALT will not:

- sell School Data or use it for advertising, marketing or building profiles of students;
- use School Data or teaching material to train AI models, or allow its sub-processors to;
- share teaching material or courses outside the School;
- use School Data for any purpose other than providing and securing the service for the School.

ECALT may use aggregated, de-identified information that can't identify a student or school (for example error rates) to operate and improve the service.

## 3. Confidentiality

ECALT ensures that everyone it authorises to process School Data is bound by confidentiality and accesses it only as needed. ECALT support access to a student's session ("view as") is logged.

## 4. Security

ECALT maintains the measures in **Annex B**, which include: encryption in transit; hashed student sign-in secrets with lockout; per-school isolation enforced in every request and tested on every release; least-privilege staff roles; audit logging of staff actions and of every teacher view of a tutor transcript; sandboxed processing of uploaded files; and pre-release security review. ECALT may update the measures as long as protection does not decrease.

## 5. Sub-processors

5.1 The School authorises the sub-processors in **Annex C**. ECALT binds each by written terms at least as protective as this DPA and stays responsible for them.

5.2 ECALT gives the School at least **[30] days'** notice of a new sub-processor (by email to the owner). The School may object on reasonable data-protection grounds; if the parties can't resolve it, the School may end the Terms and get a pro-rata refund of prepaid fees.

## 6. International transfers

School Data may be processed outside India by the sub-processors in Annex C, only in countries not restricted under section 16 of the DPDP Act. `[For EU/UK schools: Standard Contractual Clauses / UK Addendum apply.]`

## 7. Assistance and data-subject requests

7.1 The product lets the School export a student's data, export class progress, correct a student's details, archive and delete students. ECALT will help with any request the School can't handle itself.

7.2 If ECALT receives a request directly from a student, parent or staff member, it will pass it to the School and not answer it itself unless the School asks.

7.3 ECALT will give reasonable help with the School's impact assessments and with regulators.

## 8. Personal-data breach

8.1 ECALT will notify the School **without undue delay, and within [24] hours** of becoming aware of a breach affecting School Data, with what is known: nature, data and people affected, likely consequences, measures taken. It will update the School as it learns more, so the School can meet its own notice duties (including to the Data Protection Board and affected individuals within the times the DPDP Rules set).

8.2 ECALT will take reasonable steps to contain the breach and prevent it happening again.

## 9. Retention, return and deletion

9.1 While the Terms run, School Data is kept until the School deletes it. Archived students keep their data until deleted.

9.2 When the Terms end, or the School's account is terminated, ECALT keeps School Data for a **30-day grace period** (so the School can export it or reactivate), then **deletes** it: students, staff memberships, classes, courses, uploaded documents and their stored files, usage records and sign-in credentials. ECALT keeps only: the School's audit log and pseudonymised records of school authorizations, where needed to show compliance or defend legal claims. Deleted data ages out of backups within **[backup window]**.

> ⚠️ Engineering note: the automatic deletion in 9.2 is **not built yet** (SC-803). It must ship before this DPA is offered to a school with real student data.

9.3 On request, ECALT will confirm deletion in writing.

## 10. Audits

ECALT will make available information needed to show compliance with this DPA (including this DPA's annexes, its security review summary and sub-processor list) and will allow audits by the School or an independent auditor it mandates, on [30] days' notice, no more than once a year unless a breach or regulator requires it, at the School's cost, under confidentiality.

## 11. Liability and term

Liability under this DPA is governed by the Terms. This DPA lasts as long as ECALT processes School Data. If this DPA and the Terms conflict on data protection, this DPA wins.

---

## Annex A — Processing details

| | |
|---|---|
| **Purpose** | Provide ECALT for Schools to the School: build courses from the School's teaching material with AI; deliver assigned courses, quizzes and an in-course AI tutor to students; show staff progress and analytics; secure and operate the service |
| **Data subjects** | The School's students (minors and adults); the School's staff |
| **Student data** | Display name; grade; optional school reference number; class memberships; hashed sign-in secret and badge token; course progress; quiz answers, scores and hints; in-course tutor conversations; step feedback; AI usage counts; technical session and log data. **Not collected:** email, phone, birth date, photo, address |
| **Staff data** | Name, email, role, school; staff action audit log |
| **Teaching material** | Documents uploaded by staff, extracted text, AI-built courses. The School will not upload student personal data in teaching material |
| **Special categories** | None intended |
| **Duration** | Term of the Terms + 30-day grace period |
| **Processing operations** | Storage, retrieval, display to authorised users, AI generation (course building, tutoring, quizzes) via sub-processors, export, deletion |

## Annex B — Security measures

- TLS for all traffic; data encrypted at rest by the hosting providers.
- Student sign-in: class code + picture password or PIN, or a revocable QR badge; secrets stored hashed; 5 failed attempts → 15-minute lock; throttling keyed on class code + student; sessions end after 12 hours; shared-device friendly (session ends with the browser).
- Students can reach only their assigned courses and tutor (allowlist enforced on every request).
- Staff access by role (owner, admin, teacher); every school route checks membership; another school's data is indistinguishable from non-existent (404). Automated tests cover every route × role and cross-school access on every release.
- Audit log of staff actions and of every view of a student's tutor transcript.
- Uploaded files: type and size checked, macro documents refused, parsed in an isolated process with time and memory limits; only verified bytes are processed.
- AI output in courses is sanitised (no scripts, links or HTML) and every course is reviewed by a teacher before students see it.
- No advertising, no profiling of students, no re-engagement messaging to students.
- Pre-launch security review (2026-10-25) with fixes; dependency vulnerability monitoring.

## Annex C — Sub-processors

| Sub-processor | Service | Data | Location |
|---|---|---|---|
| Supabase | Database, file storage | All School Data | `[region]` |
| Railway | Application servers | All School Data in transit / processing; logs | `[region]` |
| Vercel | Web app hosting `[and analytics — see memo G5]` | Page requests | `[region / global edge]` |
| Google (Firebase Authentication) | Sign-in sessions | Staff email; student `stu_` id (no name) | `[region]` |
| OpenAI | AI generation | Teaching material text; student tutor/quiz messages | `[US]` — API terms: no training on inputs; retention `[ ]` |
| Anthropic | AI generation (if selected) | As OpenAI | `[US]` — API terms: no training on inputs; retention `[ ]` |
| Brevo | Email to staff (invites, alerts, digests) | Staff email, school name | `[EU]` |
| Sentry | Error monitoring | Technical error data, scrubbed of student content (memo G4) | `[region]` |

## Annex D — Template notice for parents

See `school-privacy-notice.md`.
