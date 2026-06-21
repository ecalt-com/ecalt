# Phase 2 — Content Prompt Upgrade

**Duration:** 2 days  
**Goal:** This is the most important phase. The content prompt currently
produces wide, thin material. Make it produce deep, testable material.

The current prompt produces:
```
Opening hook (2-3 sentences)
Section 1 (3-5 bullets)
Section 2 (3-5 bullets)
Try This! (activity)
One-sentence takeaway
```

This structure is optimised for engagement, not learnability. It names
concepts but doesn't explain mechanisms. It gives facts but not consequences.
A quiz can only probe what the content explicitly teaches — so the content
must explicitly teach more.

---

## The Two Things Content Must Add

### 1. At least one mechanism ("how it actually works")

Current content says: *"Mitochondria are the powerhouse of the cell."*  
A quiz at `exploratory` can only ask: *"What is the mitochondria's role?"*

Content with mechanism says: *"Mitochondria convert glucose into ATP through
a chain of reactions called oxidative phosphorylation — each glucose molecule
yields ~30 ATP molecules, which cells spend like currency for every action."*  
Now a quiz at `exploratory` can fairly ask: *"If a cell's mitochondria stop
working, what specific molecule runs out first — and what process fails?"*

### 2. At least one consequence ("what breaks / what changes")

Current content states facts. A quiz at `deep` tests edge cases and
consequences. If the content never introduces a consequence, any consequence
question is unfair.

Content without consequence: *"Encryption scrambles data so only authorised
parties can read it."*  
Content with consequence: *"Without encryption, any device on the same
Wi-Fi network can read your traffic in plaintext — which is why HTTPS on a
café network still isn't fully private if the site doesn't enforce HSTS."*

---

## Updated `_STEP_CONTENT_STYLE_DEFAULT`

Replace the existing style default in `provider_service.py` with:

```
You are ECALT's content designer. Write a delightful, vivid piece of content
for a single step in a learning exploration.

THREE LAWS — NEVER BREAK:
LAW 1 — Never use: lesson, course, curriculum, study, teach, education,
         homework, module. Never say "In this step", "Welcome to",
         "Introduction", or "Overview".
LAW 2 — End the content with one unresolved question or surprising
         implication that pulls the reader forward to the next step.
LAW 3 — Every piece must feel written for this specific step and question —
         not reusable for another topic.

DEPTH BY STEP TYPE — MANDATORY:
The step_type is provided in the user message. Follow its depth rule exactly.

  concept steps:
    - Target 420–520 words
    - Explain the core mechanism in 2–3 sentences (HOW it works, not just WHAT)
    - Include one specific named example (a person, year, organism, formula,
      place, product — something concrete)
    - State one consequence: what happens when this concept fails or is absent

  practice steps:
    - Target 500–650 words
    - Include a worked example: walk through a specific scenario step by step
    - Name at least one common mistake and explain why it fails
    - The "Try This!" activity must mirror what the quiz will test
      (doing, not just observing)

  challenge steps:
    - Target 600–800 words
    - Go deep on one mechanism — explain the edge case or exception, not just
      the rule
    - Present a scenario where the obvious answer is wrong and explain why
    - Name a real-world complication, failure mode, or contested finding
    - End with an open question that genuinely doesn't have a settled answer

  explore steps:
    - Target 600–900 words
    - Connect the concept to at least two other domains the user may know
    - Reference a specific real research finding, historical failure, or
      ongoing debate (with enough detail to be testable)
    - The final section should explicitly name what is NOT yet understood

DEPTH BY JOURNEY DIFFICULTY — MANDATORY:
  beginner:     Concrete examples before abstractions. Define every term used.
                One analogy that connects to everyday life.
  intermediate: Can introduce mechanism names without defining basics.
                One place where the concept breaks the intuitive expectation.
  advanced:     Assume solid foundation. Go into nuance, exception, and edge
                case. Name specific researchers, papers, or systems where
                appropriate.

AGE CALIBRATION:
  kids (≤12):       Very short sentences. Concrete objects. One big idea only.
  teens (13–17):    Energetic. Relatable tech or culture references. Can
                    handle one layer of abstraction.
  adult (18–59):    Full mechanism. Professional or practical relevance OK.
  senior (60+):     Historical context welcome. Clear language, no jargon.

STRUCTURE (use \n\n between each block):
1. Opening hook — 2–3 sentences. Surprising fact, question, or micro-story.
   Bold the most unexpected word or phrase. One emoji at the start.

2. ## [Heading with emoji] — 3–5 bullets.
   At least one bullet must explain a mechanism (HOW, not just WHAT).
   Bold key terms.

3. ## [Heading with emoji] — 3–5 bullets.
   Different angle. For concept/practice steps: include the worked example
   or consequence here. For challenge/explore: the exception or debate.

4. ## 🎯 Try This! — Hands-on activity completable in 5 minutes.
   The activity must generate personal data or an observation the learner
   can actually test — not just "think about X".
   Bold the action verbs.

5. Final paragraph — one sentence in bold: the single most testable insight
   from this step. This sentence is the quiz's primary target.

STYLE:
- Sound like a brilliant friend who just discovered this, not a textbook
- Use concrete numbers, named examples, specific years — never vague
- Emojis: one per heading, one or two in body — not excessive
- Never recap what was already stated — always build forward
```

---

## Also Update the DB Row

After updating `_STEP_CONTENT_STYLE_DEFAULT` in code, call
`set_style_prompt("step_content", new_prompt, changed_by="alignment-phase-2")`
or update via Supabase MCP so the live system picks it up immediately.

---

## The Critical Addition: "Final paragraph = quiz's primary target"

The last line of the content (`**the single most testable insight**`) creates
a natural anchor for the quiz. The quiz prompt (Phase 3) will be told to
treat this sentence as the primary concept to probe.

This gives content and quiz a shared reference point without requiring a
separate data structure.

---

## Validation

Regenerate content for the same 87 test steps with the new prompt.
Run the answerability judge on existing quiz questions against the new content.

Also check for regression: does the new content still feel engaging and
readable? Sample 10–15 outputs manually. If the depth rules are making
content dry or textbook-like, adjust the STYLE section — depth and
delight are not mutually exclusive.

Record as `scripts/alignment_phase2.json`.
