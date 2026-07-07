# Course Content Quality Upgrade Plan

**Problem:** Users report journey/spark course content is generic — it reads like it could be about any topic, every step looks structurally identical, and depth doesn't match the learner.

---

## Implementation status (2026-07-07)

| Phase | Status | Notes |
|---|---|---|
| 1a Models | ✅ **LIVE in prod** | journey → gpt-4.1, step_content → gpt-4.1-mini, spark → gpt-4.1-mini (`ai_provider_config`) |
| 1b Prompt reset | ✅ **LIVE in prod** | Stale DB prompts NULLed (backup: `prompt-backup-2026-07-07.md` + `ai_prompt_history`); code defaults now active |
| 2 Context passing | ✅ code done, **needs deploy** | difficulty/purpose/expertise/outline/position/covered-facts into step content; token caps 3200/3000/1000; warm task logs + retries |
| 3 Richer blueprints | ✅ code done, **needs deploy** | `core_question` + `seed_facts` per step; 250-char descriptions; per-type content skeletons; contrast few-shot; transition seed. Structured outputs: deferred |
| 4 Versioning + critic | ✅ code done, migration **applied to prod** | `step_content.model/prompt_version/generated_at`; nano critic (`content_critic` type) w/ one retry, fails open; lazy background refresh of v1 content; `POST .../content/regenerate` (10/hr) |
| 5 Feedback loop | ✅ partial, **needs deploy** | `step_feedback` table + `POST .../feedback`; negative tags auto-regenerate. Deferred: behavior-based fingerprint, weekly quality report |
| 0 Benchmark harness | ⏳ deferred | Smoke-tested end-to-end instead (blackhole journey: all steps got specific seed facts; step content 461 words, 4 grounded anchors) |
| 6 Grounding | ⏳ deferred | Revisit only if niche topics still weak |

Frontend implemented (2026-07-07): `StepFeedbackBar` component (thumbs + tag chips + "Fresh take" regenerate) wired into `StepNode` for signed-in users; endpoint reference in `docs/step-feedback-and-regenerate.md`.
Tests: suite green except one pre-existing unrelated failure (`TestChatStream::test_custom_interaction_type_passed_to_stream_chat`).

**Deploy note:** prod DB is already on new models/prompts/migration and is fully compatible with the old deployed code; the Phase 2–5 behavior activates when the backend deploys. After deploy, the 622 v1 cached steps lazily regenerate as users view them.

**Scope:** Everything that generates course-related content:
- `POST /explore` + `/explore/preview` + `/explore/confirm` → `generate_journey()` (`app/services/ai_service.py:266`)
- Step content: `GET /journeys/{id}/steps/{id}/content` + `warm_journey_steps()` (`ai_service.py:83,120`)
- `POST /spark` → `generate_spark()` (`app/services/spark_service.py:165`)
- Daily spark → `generate_daily_spark()` (`spark_service.py:106`)
- Model/prompt config: `ai_provider_config` table via `provider_service.py`

---

## Diagnosis — why the content is generic (ranked by impact)

### 1. Production runs the cheapest models available ⚠️ CONFIRMED IN PROD DB
`ai_provider_config` (live Supabase, checked 2026-07-07):

| interaction_type | prod model | notes |
|---|---|---|
| `journey` | **gpt-4.1-nano** | cheapest model in catalog — generates the entire course skeleton |
| `spark` | **gpt-4.1-nano** | answer + mission |
| `daily_spark` | **gpt-4.1-nano` | fine for a 1-line question |
| `step_content` | gpt-4o-mini | writes the actual lesson body |

Nano-class models cannot reliably produce specific named examples, mechanisms, and numbers. This alone explains most of the "generic" feedback.

### 2. Stale prompt overrides in prod DB shadow the good prompts in code ⚠️ CONFIRMED
Every interaction type has a custom `style_prompt` in `ai_provider_config` (set 2026-06-01, except `quiz` updated 2026-07-07). The prod `step_content` prompt is **1,324 chars** — an old version. The code default `_STEP_CONTENT_STYLE_DEFAULT` (`provider_service.py:147`) is ~3,500 chars with depth-by-step-type, depth-by-difficulty, and age calibration rules — **it never runs in prod** because a non-NULL DB row wins (`get_config`, `provider_service.py:534`).

### 3. Step content is generated context-blind
`generate_step_content()` user message (`ai_service.py:93-101`) contains only: journey title, original question, step title, step description, step type, age group. It is missing:
- **Journey difficulty** — the style prompt has a MANDATORY "DEPTH BY JOURNEY DIFFICULTY" section (`provider_service.py:192`) but the model is never told the difficulty → always defaults to middle-generic. This is a straight bug.
- **`learner_purpose` / `topic_expertise`** — collected at explore time, persisted on the `journeys` row (`explore.py:210`), then never used again. A "research paper / expert" journey gets the same step content as "fun / beginner".
- **The rest of the journey** — no sibling step titles, no step position (step 2 of 8?), no awareness of what earlier steps already covered → steps repeat the same hook facts and can't "build forward" despite the prompt demanding it.

### 4. Thin step specs starve the content generator
The journey contract caps step descriptions at **120 characters** (`provider_service.py:142`). That ≤120-char line is the *only* topical seed for 400–900 words of lesson content. The step-content model has to invent the substance itself — a nano/mini model invents generic filler.

### 5. One rigid template for every step of every course
`_STEP_CONTENT_CONTRACT` (`ai_service.py:34`) forces the identical skeleton every time: emoji hook → two "## heading + 3-5 bullets" sections → "## 🎯 Try This!" → bold final sentence. Even with perfect facts, every step *feels* mass-produced. Perceived genericity is structural, not just factual.

### 6. Token ceilings force shallow output
- `step_content`: `max_tokens=2000` (`ai_service.py:108`) vs. prompt targets of 600–900 words *plus* 3–5 quiz anchors in the same JSON — explore/challenge steps hit the ceiling or self-truncate.
- `spark`: `max_tokens=750` (`spark_service.py:173`) for answer + full mission JSON.
- `journey`: 2048 for up to 12 steps.

### 7. Cache is permanent and unversioned — improvements never reach users
- `step_content` rows have no model/prompt version; `warm_journey_steps` inserts with `ON CONFLICT DO NOTHING` (`ai_service.py:159`).
- Any prompt/model improvement only affects *new* journeys; every existing journey keeps its generic content forever.
- `warm_journey_steps` swallows every error with bare `except: pass` (`ai_service.py:165`) — failed generations are invisible.

### 8. Personalization almost never activates
- Cognitive fingerprint injection requires confidence ≥ 0.3 built **only from chat messages** (`fingerprint_service.py`). Users who go straight to journeys (most of them) never build one → `inject_fingerprint` is a no-op.
- `_build_learning_context()` (prior journeys, strong/weak concepts) is injected into journey generation only — never into step content.

### 9. No measurement, no feedback, brittle parsing
- No genericity/quality metric exists; nobody can tell if a change helps.
- No per-step user feedback ("too generic", "too basic") is collected.
- JSON is scraped with `find("{")`/`rfind("}")` instead of OpenAI structured outputs → malformed/truncated responses burn retries or 502.

---

## Phase 0 — Baseline & audit (½ day, no user impact)

**Goal:** Make quality measurable before changing anything.

1. **Benchmark set.** Create `scripts/content_quality_benchmark.py` (extend existing `scripts/test_journey_generation.py`): ~20 fixed questions spanning mainstream ("How does DNA work?"), niche ("How do CRDTs resolve conflicts?"), kids, and expert/research-purpose profiles. For each: generate journey + content for 3 steps (first / middle / last).
2. **LLM-as-judge rubric** (strong model, e.g. gpt-4.1 or Claude Sonnet), scoring 1–5 on:
   - **Specificity**: named people/places/systems, real numbers, at least one mechanism (HOW).
   - **Topicality**: "Could this paragraph appear unchanged in a course on a different topic?"
   - **Progression**: does step N build on N-1 or repeat it?
   - **Calibration**: does depth match the requested difficulty/expertise?
3. **Run against current prod config** → save `scripts/content_quality_baseline.json`.
4. **Config audit doc:** diff each prod `style_prompt` in `ai_provider_config` against `DEFAULT_STYLE_PROMPTS`; record which rows are stale (expect: all set 2026-06-01 except quiz).

**Exit criteria:** baseline scores recorded; audit table written into this folder.

---

## Phase 1 — Zero-code production fixes (1 day — biggest single win)

**Goal:** Stop shadowing the good prompts; stop using nano models for course content. All via `ai_provider_config` writes (admin UI or `set_style_prompt`/`set_config` so `ai_prompt_history` audit is preserved). **No deploy needed** — but remember: prod behavior = DB row, not code (see memory note).

1. **Reset stale prompts to code defaults** (`reset_to_default=True`) for `step_content`, `journey`, `spark` — instantly activates the rich depth/difficulty/age-calibrated prompts that already exist in `provider_service.py`.
2. **Upgrade models** in DB:
   - `journey`: gpt-4.1-nano → **gpt-4.1** (or `claude-sonnet-4-6`). The skeleton determines everything downstream — this is the highest-leverage call in the system.
   - `step_content`: gpt-4o-mini → **gpt-4.1-mini** minimum; A/B a sample with gpt-4.1/Sonnet.
   - `spark`: gpt-4.1-nano → **gpt-4o-mini or gpt-4.1-mini** (user-facing first impression; keep latency in mind).
   - Leave `daily_spark` on nano (one-line output).
3. **Cost check:** pull last-30-day token volume per interaction_type from the usage table; compute projected delta. (Rough per-unit: a journey ≈ 1.5k out tokens → nano $0.00006 vs 4.1 $0.0012 — still fractions of a cent; step content ≈ 2k out → 4o-mini $0.00012 vs 4.1-mini $0.00032. Expect total AI spend to stay small; verify with real volume.)
4. **Re-run Phase 0 benchmark** on new config; record scores.

**Exit criteria:** benchmark specificity/topicality up materially; cost delta approved.

---

## Phase 2 — Fix context starvation (2–3 days, backend code)

**Goal:** The step-content model knows *who* it's writing for and *where* the step sits in the course.

1. **Pass the missing context into `generate_step_content()`** (`ai_service.py:83`):
   - `difficulty` (journey.difficulty) — fixes the dead "DEPTH BY DIFFICULTY" prompt section.
   - `learner_purpose`, `topic_expertise` (read from `journeys` row in `get_step_content` and `warm_journey_steps` callers).
   - `journey outline`: numbered list of all step titles + this step's position ("Step 3 of 8").
2. **Build-forward continuity in `warm_journey_steps()`:** generation is already sequential — accumulate a running "already covered" block (previous step titles + their quiz-anchor facts, capped ~800 chars) and pass it with an instruction: *"These facts are already covered — do not repeat them; build on them."* For the on-demand cache-miss path, fetch existing `step_content.quiz_anchors` for earlier steps of the same journey.
3. **Inject `_build_learning_context()` into step content** for signed-in users (currently journey-gen only).
4. **Raise token ceilings:** `step_content` 2000 → 3200; `spark` 750 → 1000; `journey` 2048 → 3000.
5. **Kill silent failures:** replace `except: pass` in `warm_journey_steps` with logged warning + one retry; emit a counter (log-based is fine) for failed warms.

**Exit criteria:** benchmark "progression" and "calibration" scores improve; a journey generated with expertise=expert visibly differs from beginner on the same question.

---

## Phase 3 — Richer blueprints + varied structure (3–4 days)

**Goal:** Give the content writer real substance to work from, and stop every step looking identical.

1. **Extend `_JOURNEY_CONTRACT`** (`ai_service.py:13`) — per step, add:
   ```json
   {
     "title": "...",
     "description": "... (raise cap 120 → 250 chars)",
     "core_question": "The one question this step answers",
     "seed_facts": ["2-3 specific facts/examples/mechanisms to build the step around"],
     "type": "...", "estimated_minutes": 15
   }
   ```
   Persist in the `steps` jsonb (backwards-compatible — old rows just lack the keys). Feed `core_question` + `seed_facts` into step-content generation. The (now stronger) journey model does the topical research once; the step writer elaborates instead of inventing.
2. **Vary structure by step type** in `_STEP_CONTENT_CONTRACT`: keep "Try This!" for practice/challenge, but give concept/explore steps 2–3 alternative skeletons (narrative-led, mechanism-led, controversy-led) and let the model pick. Remove the mandatory-emoji-per-heading rule for adult/advanced content.
3. **Add contrast few-shots** to journey + step prompts: one BAD (generic) vs GOOD (specific) example pair each — cheap models respond strongly to contrast examples.
4. **Structured outputs:** in `complete_text` (`provider_service.py:713`), use OpenAI `response_format={"type": "json_schema", ...}` (and Anthropic tool-use equivalent) for journey/step/spark, keyed off an optional `json_schema` param. Eliminates `find("{")` scraping, parse retries, and truncation-induced 502s.
5. Update `AVAILABLE_MODELS` catalog while in the file (add current-gen models so admins can select them).

**Exit criteria:** two journeys on adjacent topics produce visibly different step structures; JSON parse-retry rate ~0.

---

## Phase 4 — Quality gate + cache versioning (2–3 days)

**Goal:** Bad generations never reach users; existing generic content gets refreshed.

1. **Migration:** add `model`, `prompt_version`, `generated_at` columns to `step_content`; define `CONTENT_PROMPT_VERSION` constant in code, bump on any prompt change.
2. **Critic pass (cheap):** after generating step content, run a nano-model check scoring specificity/topicality (counts named entities/numbers, asks the "any-topic?" question). Below threshold → regenerate once with the critic's complaint appended. Apply on both warm and cache-miss paths; log scores.
3. **Lazy refresh:** on cache read, if `prompt_version < CONTENT_PROMPT_VERSION` and the user is actively viewing, serve stale content but queue a background regeneration (budget-checked) so active journeys upgrade over ~days.
4. **User-facing "Regenerate this step"** button hook: `POST /journeys/{id}/steps/{id}/content/regenerate` — budget-checked, rate-limited (e.g. 2/step/day), overwrites cache. (Frontend work: document in an md per frontend-docs convention, don't implement UI here.)

**Exit criteria:** every new `step_content` row is versioned; regeneration path verified end-to-end; critic rejection rate logged.

---

## Phase 5 — Feedback loop + broader personalization (3–4 days)

**Goal:** Learn from users instead of guessing.

1. **Per-step feedback endpoint:** `POST /journeys/{id}/steps/{id}/feedback` with `rating` (up/down) + optional tag (`too_generic | too_basic | too_advanced | inaccurate | loved_it`) → new `step_feedback` table. (Frontend: md doc.)
2. **Wire feedback into regeneration:** a `too_generic`/`too_basic` tag triggers the Phase 4 regeneration with the tag as refinement context.
3. **Fingerprint from behavior, not just chat:** feed quiz performance (`concept_interactions`), journey difficulty choices, and step dwell/completion into fingerprint updates so `inject_fingerprint` activates for non-chat users.
4. **Weekly quality report:** scheduled job (or manual script) running the Phase 0 judge on a sample of the week's real generations + feedback-tag rates; track trend.

**Exit criteria:** feedback rows flowing; "too_generic" tag rate becomes the north-star metric to drive down.

---

## Phase 6 (optional, later) — Grounding for niche/current topics

For questions where parametric knowledge is weak (niche tech, current events), add a retrieval step before journey generation: web search (or curated sources) → 3-5 snippets injected as "source material — ground seed_facts in these". Gate behind topic-detection to control cost/latency. Only pursue if Phase 1–4 benchmarks still show weakness on the niche slice.

---

## Rollout order & safety

| Phase | Risk | Rollback |
|---|---|---|
| 1 | None (config) | `ai_prompt_history` keeps old prompts; `set_config` back to old model |
| 2–3 | Prompt regressions | Benchmark gate before deploy; prompts also live in DB so can hot-revert |
| 4 | Cost from regeneration | Budget-check + rate limits already exist; lazy refresh is queue-throttled |
| 5 | Low | Feature-flag feedback UI |

**Every phase exits through the Phase 0 benchmark — no phase ships without a score comparison.**

Key files:
- `app/services/ai_service.py` — journey + step content generation, contracts
- `app/services/spark_service.py` — spark + daily spark
- `app/services/provider_service.py` — models, default prompts, `complete_text`
- `app/api/v1/endpoints/explore.py`, `journeys.py`, `spark.py` — entry points
- `ai_provider_config` (Supabase) — **prod truth for model + prompt; changes need a DB write, not just a code edit**
