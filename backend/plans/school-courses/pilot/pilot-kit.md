# Pilot school kit (SC-003, #9)

Everything needed to recruit one pilot school and collect the eval-corpus documents. Recruiting is a people task; this kit makes the asks concrete. `[ ]` = fill in.

## 1. What we're asking for

| | |
|---|---|
| **Who** | One school in India (D3), ideally grades 5–10, with 2–4 teachers willing to try it and one admin contact |
| **Length** | One term (~10 weeks): 2 weeks setup, 6 weeks classroom use, 2 weeks wrap-up |
| **Scale** | 2–4 classes, up to ~150 students, 3–6 courses built from the teachers' own material |
| **Cost to school** | Free for the pilot `[confirm]`; ECALT pays AI costs up to a set monthly budget |
| **Time from teachers** | ~2 h setup each, ~30 min/week feedback |
| **Two separate asks** | (a) use the product in class; (b) *optionally* let us keep 10–20 of their teaching documents for testing (§4) |

## 2. Before the first student is added (gates)

- [ ] Counsel-approved school terms + DPA signed (#7) — the in-app DPA text replaced and version bumped.
- [ ] Offboarding deletion built (SC-803) — the DPA promises it.
- [ ] Sub-processor terms confirmed; Sentry scrubbing; analytics off for student sessions (compliance memo G3–G5).
- [ ] School has sent parents the privacy notice (`legal/school-privacy-notice.md`) if its rules require.
- [ ] `SCHOOLS_ENABLED` on in prod for the pilot (runbook, #10).

Until then a school can still be shown the product on **dev** with made-up students.

## 3. Outreach email (template)

> **Subject:** Pilot invitation — turn your own lesson material into interactive courses
>
> Dear [Name],
>
> We're inviting a small number of schools to pilot **ECALT for Schools** this term, free of charge.
>
> Your teachers upload material they already use — a chapter, notes, a worksheet (PDF or Word). ECALT drafts a step-by-step course from it, with short quizzes and a tutor that answers students' questions *from that material*. Teachers review and edit everything before students see it, and see each student's progress afterwards.
>
> Built for schools from the start: students sign in with a class code and a picture password or PIN — no email addresses; we keep only a first name and grade; nothing is used for advertising or sold; your school stays in control of its data and can export or delete it at any time.
>
> We'd ask for 2–4 teachers and one admin contact for about 10 weeks, plus short feedback calls. Could we show you a 20-minute demo on [dates]?
>
> [Name, role, phone] · support@ecalt.com

Attach: the demo video (#22) and a one-page summary of §1 and the privacy points.

## 4. Eval-corpus documents — permission form

Teaching documents let us test course quality on real material (feeds `scripts/school_eval_corpus/` and `school_update_eval_corpus/`, SC-007/411/607). Collect **10–20**: a mix of subjects and grades, English + Hindi, at least two revised-edition pairs (for update tests), some with tables/maths, one scanned (to test detection).

> **Permission to use teaching documents for testing**
>
> School: [ ] · Contact: [ ] · Date: [ ]
>
> 1. **Documents.** The documents listed below, provided by the school ("Documents").
> 2. **Use.** ECALT may store the Documents and use them **only to test and improve the quality of ECALT's course-building**, including running them through its AI providers under terms that forbid training on them. ECALT will not publish, sell or share the Documents, or show them to anyone outside ECALT's team and its sub-processors.
> 3. **No student data.** The school confirms the Documents contain **no personal data of students** (no names, marks, photos). ECALT will delete any it finds.
> 4. **Rights.** The school confirms it owns the Documents or may grant this permission (e.g. teacher-made material). Commercial textbooks: list the publisher; we may need the publisher's permission instead.
> 5. **Duration.** Until the school withdraws permission by emailing support@ecalt.com; ECALT then deletes the Documents and anything derived from them within 30 days.
> 6. **Credit.** None, unless the school asks.
>
> | # | Title | Subject / grade | Language | Author / owner | Notes |
> |---|---|---|---|---|---|
> | 1 | | | | | |
>
> Signed for the school: ______ (name, role) · For ECALT: ______

Store signed forms with the documents' provenance (`docs/eval-corpus-permissions/` — **outside** the repo if it holds names; record only form IDs in the repo).

## 5. Running the pilot

| Week | What |
|---|---|
| 0 | DPA + terms signed; ECALT admin creates the school (seats, AI budget); owner invite sent |
| 1 | Staff sign in, accept DPA, add classes + students (CSV), print login cards; teachers upload first documents |
| 2 | Teachers build + publish first course each; dry run with a few students |
| 3–8 | Classroom use; weekly 30-min feedback call; watch usage page + job failures |
| 9 | Teacher + student survey; export progress |
| 10 | Wrap-up call: continue / stop. If stopping, school exports data; termination starts the 30-day deletion |

## 6. Success measures

| Measure | Target |
|---|---|
| Teachers publish a course from their own material | ≥ 80 % of pilot teachers, ≥ 3 courses total |
| Time from upload to published course | median < 30 min of teacher time |
| Teacher edits needed | ≤ 1 in 5 steps substantially rewritten |
| Grounding issues reported by teachers | 0 unsupported claims reaching students |
| Students who start an assigned course | ≥ 70 % |
| Sign-in problems | < 5 % of sessions need teacher help after week 1 |
| AI cost per student per month | within budget `[ ]` |
| Security / privacy incidents | 0 |

## 7. Status

- [ ] Shortlist schools `[ ]`
- [ ] Demo held
- [ ] School agreed
- [ ] Documents collected (__ / 10–20) with signed permission
