# Compliance memo — ECALT for Schools pilot

> **DRAFT for counsel review — not legal advice.** Prepared by the engineering team on 2026-10-25 so counsel can see exactly what the system does. Statements about the law are our reading and must be confirmed. `[ ]` marks facts still to fill in. Tracker: SC-002 (#7). Companion drafts in this folder: `school-terms.md`, `dpa-template.md`, `school-privacy-notice.md`.

## 1. Summary

- **Roles.** The school decides why and how student data is processed (controller / Data Fiduciary / FERPA "school official" relationship). ECALT processes it only to run the service on the school's instructions (processor / Data Processor). The product is built around that split: a school can't add a student until its owner accepts the DPA (`409 dpa_required`), and every student's creation is recorded as a school authorization.
- **Pilot jurisdiction: India** (decision D3), under the DPDP Act 2023 and the DPDP Rules 2025. US (COPPA + FERPA) and EU/UK (GDPR) come later and are covered here only to flag what would change.
- **We believe the design fits a school-authorised model**: minimal student identity (display name, grade, optional school reference — no email, birth date or photo), no advertising, no profiling outside the course, students limited to assigned courses, staff actions audited, export and deletion per student.
- **Before real student data**, these must be closed (details in §6): the offboarding deletion the DPA already promises isn't built yet (SC-803); the in-app DPA text is a placeholder; sub-processor terms and regions need confirming (especially the AI providers); error reporting and web analytics need tightening for student sessions.

## 2. What the service does with student data

### 2.1 Who is involved

| Party | Role | Identity | How they sign in |
|---|---|---|---|
| School owner / admin | Staff (adult) | Google account (email) | Google sign-in |
| Teacher | Staff (adult) | Google account (email) | Google sign-in |
| Student | Child (any age in the school) | `stu_…` id, display name, grade, optional school reference number | Class code → pick name → picture password or 6-digit PIN, or a printed QR badge. No email, no password reset by email |
| ECALT admin | Operator support | ECALT staff account | Google sign-in + admin flag; can view a user's session ("impersonation"), which is audited |

### 2.2 Data inventory (students)

| Data | Source | Purpose | Where |
|---|---|---|---|
| Display name, grade, optional school reference number | School staff (manual or CSV import) | Identify the student to their teacher; pitch content to the grade | Postgres (`school_students`) |
| Class memberships | School staff | Which courses the student sees | Postgres |
| Login secret (picture sequence or PIN) and badge token | Generated / set by staff | Sign-in | Stored **hashed** only; 5 wrong attempts → 15-min lock |
| Course progress, quiz answers and scores, hints used | Student activity | Learning + teacher progress view | Postgres |
| Tutor conversations (in-course AI tutor) | Student messages + AI replies | Help the student; teacher safeguarding view (D4, school can switch off; disclosed to the student) | Postgres; message text is sent to the AI provider to generate replies |
| Step feedback (thumbs / short text) | Student | Improve the course | Postgres |
| AI usage counts and cost | System | School budget metering | Postgres |
| Sign-in session (Firebase) | System | Keep the student signed in, max 12 h; browser-session storage on shared devices | Firebase Authentication (Google) |
| Technical logs (request path, status, timing; error reports) | System | Operate and secure the service | Railway logs; Sentry (see §6, G4) |

Staff data: name, email, role, school; staff actions in an audit log (`school_audit_log`).

Teaching material: PDFs / Word files uploaded by staff, their extracted text, and the AI-built courses. Private to the school; never shared outside it (D11, enforced in the database). **Uploaded material may itself contain personal data** (e.g. a worksheet with student names) — see G8.

### 2.3 AI processing

- Course building: document text → AI provider → draft course. A teacher reviews and publishes; nothing reaches students unreviewed.
- Tutor and quizzes for students: the student's message, the step content and a grade band ("kids"/"teens", derived from class grade) are sent to the provider. No name, school or contact data is included in the tutor or quiz prompts (checked in code 2026-10-25).
- Provider and model per task are configurable (OpenAI and Anthropic today). **No training on customer data** must be guaranteed contractually — see G3.
- **No profiling.** The consumer product builds a knowledge profile and a "cognitive fingerprint" from chats and queues re-engagement nudges. The review found this ran for school students too; **fixed 2026-10-25** — for students only usage metering runs after a tutor turn (`chat_service._post_stream_bg`, `tests/unit/schools/test_student_no_profiling.py`).
- No automated decision with legal or similarly significant effect is made about a student. Quiz scores are formative.

### 2.4 Rights and lifecycle (as built)

| Action | Who | Built? |
|---|---|---|
| Export one student's data (JSON) | School admin | ✅ |
| Export class progress (CSV) | Staff | ✅ |
| Delete a student (cascade incl. Firebase login) | School admin | ✅ |
| Archive students (year end; blocks login, keeps data) | School admin | ✅ |
| Teacher views a tutor transcript | Class teacher / admin, when enabled; each view audited | ✅ |
| School leaves → 30-day grace → full deletion | System | ❌ **not built (SC-803)** |
| Breach notification runbook | ECALT | ❌ (SC-806) |

## 3. India — DPDP Act 2023 and DPDP Rules 2025

Our reading, for counsel to confirm:

1. **Children are everyone under 18.** A Data Fiduciary must obtain verifiable parental consent before processing a child's data (s. 9(1)) and must not track, behaviourally monitor or target advertising at children (s. 9(3)).
2. **Educational-institution exemption.** The Rules exempt processing by educational institutions from s. 9(1) and 9(3) to the extent needed for educational activities or children's safety. **Question for counsel (Q1):** does this exemption extend to a Data Processor acting under contract for the institution, and does it cover AI-tutoring and progress analytics as "educational activities"? Our design assumes yes, with the school as Fiduciary.
3. **Processor contract.** A Fiduciary may engage a Processor only under a valid contract (s. 8(2)). The DPA draft is that contract. The Fiduciary stays responsible for compliance, including the Processor's.
4. **Security safeguards and breach notice.** Reasonable safeguards are required (s. 8(5)); on a breach the Fiduciary must notify the Board and affected individuals (the Rules set an initial notice without delay and a detailed report within 72 hours). The DPA commits ECALT to notify the school promptly with what it needs.
5. **Erasure.** Data must be erased when the purpose is served or consent withdrawn, unless retention is legally required (s. 8(7)); the Processor must erase too. This is why SC-803 (offboarding deletion) is a blocker.
6. **Cross-border transfer** is allowed except to countries the Government restricts (s. 16). Our sub-processors process outside India `[confirm regions — G3]`. **Q2:** any state-board or school-level data-residency expectations for the pilot school?
7. **Timeline.** The Rules phase in obligations over roughly 18 months from notification `[confirm exact dates]`. We plan to comply from the pilot onward rather than rely on the transition.
8. **Q3:** for a private school, does any additional state education regulation apply to edtech vendors (e.g. vendor empanelment, content approval)?

## 4. United States (later) — COPPA and FERPA

- **COPPA.** The FTC's guidance lets a school authorise collection from under-13s in place of parents when the data is used **only for the school's educational purpose** and not for commercial purposes. The amended COPPA Rule (2025) did not codify a school-authorization exception, so this still rests on guidance. Requirements we already meet: no ads, no commercial use, school can review and delete. **Gaps for a US launch:** a written data-retention policy published to schools, a direct notice to the school, and confirming the AI-provider terms meet COPPA's third-party disclosure rules.
- **FERPA.** ECALT would act as a "school official" with a legitimate educational interest under the school's direct control, with no re-disclosure. The DPA language in `dpa-template.md` is written to support this.
- **State student-privacy laws** (e.g. California SOPIPA, New York Ed Law 2-d) add vendor-contract terms; many schools ask vendors to sign the Student Data Privacy Consortium's agreement. Out of scope for the pilot.

## 5. EU / UK (later) — GDPR

- Art. 28 processor terms: covered by the DPA draft (instructions, confidentiality, security, sub-processors, assistance, deletion/return, audits).
- The school needs a lawful basis (usually public task or legitimate interest — not child consent, so Art. 8 is generally not engaged). A **DPIA** is needed (children + innovative technology/AI) — extend `docs/children-data-dpia.md` (SC-804).
- International transfers: SCCs (EU) / IDTA or Addendum (UK) with each sub-processor; transfer impact assessments.
- UK Children's Code (AADC) applies to services likely to be accessed by children: high-privacy defaults, no nudges, no profiling by default.

## 6. Gaps to close before real student data

| ID | Gap | Why | Fix | Ticket |
|---|---|---|---|---|
| **G1** | Offboarding deletion not built, but the DPA modal already promises it | Erasure duty (DPDP s. 8(7)); we'd be in breach of our own terms | Build terminated → 30-day grace → deletion job (DB, storage, Firebase) and verify nothing remains | SC-803 |
| **G2** | In-app DPA text is a summary placeholder | Acceptance must be of the real agreement | Put counsel-approved text (or a link to it) in `DpaModal`, bump `SCHOOL_DPA_VERSION` so owners re-accept | SC-804 |
| **G3** | Sub-processor terms and regions unconfirmed | Processor-contract chain; cross-border; children's data to AI | Confirm and record for each: Supabase (DB, storage) `[region]`, Railway (API) `[region]`, Vercel (web, analytics) `[region]`, Google Firebase Authentication, OpenAI and Anthropic (API terms: no training on inputs, retention period, zero-data-retention eligibility), Brevo (staff email only), Sentry (errors). Publish the list in the DPA annex | SC-002 |
| **G4** | Error reports may include student data | Sentry's defaults can attach request bodies and URLs (student ids, display names, tutor text) | Server: `max_request_body_size="never"`, a `before_send` scrubber; client: no replay, strip query/body. Tag `school_id` only | SC-805 |
| **G5** | Web analytics runs on student pages | DPDP s. 9(3) "tracking" concern even if cookieless | Don't mount Vercel Analytics / Speed Insights for school-student sessions (or confirm counsel is comfortable with cookieless aggregate page views) | new |
| **G6** | No breach-notification runbook | DPA promise + Fiduciary's 72-h duty | Write the runbook (who, how fast, what data) | SC-806 |
| **G7** | DPIA has no schools section | Accountability; GDPR later | Add: shared devices, teacher transcript visibility, uploaded documents, AI providers | SC-804 |
| **G8** | Uploaded teaching material may contain student personal data | It is sent to AI providers during course building | Terms: school must not upload student personal data in teaching material; upload screen reminder | SC-002 / FE |
| **G9** | Retention for logs and backups not stated | Erasure + transparency | State Railway log retention and Supabase backup window `[ ]`; deleted data ages out of backups within that window | SC-803 |

## 7. Questions for counsel

1. (Q1) Educational-institution exemption under the DPDP Rules: does it cover ECALT as Processor, and AI tutoring + progress analytics?
2. (Q2) Data-residency expectations for the pilot school / its board.
3. (Q3) Any state edtech-vendor rules for the pilot state.
4. Is school authorization alone enough, or should schools also send parents a notice (we drafted `school-privacy-notice.md` so schools can)?
5. Teacher access to tutor transcripts (D4, on by default, disclosed, school can turn off): acceptable default, or should it be off by default?
6. Copyright: is the school's warranty in the terms (rights to uploaded material) enough, or do we need a takedown process?
7. Liability cap and indemnities appropriate for a free pilot vs paid.
8. Governing law and venue `[ ]`.
