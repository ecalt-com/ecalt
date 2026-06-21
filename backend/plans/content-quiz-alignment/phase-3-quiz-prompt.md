# Phase 3 — Quiz Prompt Tightening

**Duration:** 1 day  
**Goal:** Update the quiz prompt to work in partnership with the richer content
from Phase 2. Specifically: teach the quiz generator to target the content's
explicit mechanisms and consequences rather than inferring beyond them.

Phase 2 made the content deeper. Phase 3 makes the quiz draw from exactly
what Phase 2 added.

---

## Key Changes to `_QUIZ_STYLE_DEFAULT`

### 1. Anchor to the final sentence

Phase 2 content now ends with:
> `**[the single most testable insight from this step]**`

The quiz should treat this as its primary target:

```
PRIMARY TARGET:
The content ends with a bolded sentence — this is the step's single most
testable insight. Your question should test whether the learner understood
THAT insight, at the depth level specified by question_depth.

surface      → Can the learner restate this insight in their own words?
exploratory  → Can the learner apply this insight to a new scenario?
deep         → Can the learner identify when this insight breaks down?
research     → Can the learner connect this insight to an open question
               in the field?
```

### 2. Mechanism-first questioning

Replace the existing rule 1 with a more concrete version:

```
QUESTION DESIGN RULES:

1. Test the MECHANISM, not the label.
   The content explains HOW something works. Test that explanation.

   BAD  (tests the label): "What is photosynthesis?"
   BAD  (tests a detail not in content): "What is the quantum yield of PS2?"
   GOOD (tests the mechanism in content): "A plant is kept in total darkness
        for 3 days. Which part of photosynthesis stops immediately — and
        which keeps running briefly on stored molecules? Use what the content
        explains about the two stages."

   If the content does not explain the mechanism, do not ask about it.
   Ask about what the content DOES explain, at the appropriate depth.
```

### 3. Consequence and exception questions (for deep/research)

```
FOR deep AND research QUESTIONS ONLY:
   The content includes a consequence (what happens when the concept fails)
   or an exception/edge case. Your question should probe THAT consequence
   or exception.

   If the content does not explicitly describe a consequence or exception,
   do NOT generate a deep or research question. Downgrade to exploratory.
   A question that invents an edge case the content never introduced
   is unfair regardless of intellectual quality.
```

### 4. Stronger content boundary enforcement

```
CONTENT BOUNDARY — ENFORCED:
Before finalising your question, ask yourself:
  "Could a learner who read ONLY this content — with no prior knowledge
   of this topic — reasonably answer this question?"

If the answer is NO:
  - The question references a term the content doesn't define → remove it
  - The question requires a step the content skips → simplify to what
    the content does cover
  - The question asks about implications the content never draws → replace
    with an application of something the content does state explicitly

A question that fails this check is a wrong answer regardless of how
well-crafted it otherwise is.
```

---

## Updated Hint System

Phase 2 content is now richer. Update hints to draw from that richness:

```
HINT SYSTEM — 3 progressive hints:
   Hint 1: Points to the section of content where the answer lives.
            "Think about the part that explains [mechanism name]."
   Hint 2: Quotes or closely paraphrases a specific sentence from the
            content that contains the key insight.
   Hint 3: States the correct reasoning path in plain language, stopping
            one sentence short of the answer.
   RULE: No hint ever states the answer directly.
   RULE: Every hint must be traceable to something in the content.
```

---

## Updated Grading System (`_GRADE_SYSTEM`)

The grader also needs updating. Currently it can mark correct answers wrong
when the learner uses different terminology from the model answer but correctly
demonstrates understanding of the mechanism.

Add to `_GRADE_SYSTEM`:

```
MECHANISM CREDIT RULE:
If the learner correctly describes the mechanism or consequence — even in
informal language, even without using the technical term — mark CORRECT.
Understanding matters more than vocabulary.

EXAMPLE:
  Model answer: "Oxidative phosphorylation produces 30–32 ATP molecules."
  Student says: "The cell gets about 30 units of energy from breaking down
               one sugar molecule using oxygen."
  → CORRECT. They understand the mechanism even without the technical name.

FABRICATION RULE:
If the learner adds a specific claim that contradicts or goes beyond what
the content stated — even alongside something correct — mark INCORRECT and
address the fabricated claim explicitly in feedback.
```

---

## Validation

Re-generate quiz sets for the 87 test steps using the updated quiz prompt
(with Phase 2 content as input). Run the answerability judge.

Also run a small manual check: for 10 questions, manually verify that the
question targets what the content explicitly covers. Look for any case where
the model still invents details beyond the context.

Record as `scripts/alignment_phase3.json`.

Expected combined score after Phases 1+2+3: **65–78%** answerability.
