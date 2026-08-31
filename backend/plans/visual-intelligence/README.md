# Visual Intelligence Layer — Implementation Plan

**Source spec:** ECALT Visual Intelligence v1 — CTO Architecture & Claude CLI Implementation Specification (pasted 2026-08-30).
**Status:** Phases 1 + 2 implemented 2026-08-30 (uncommitted). Migration `010_visual_intelligence_foundation.sql` **applied to prod DB**. Orchestrator is now wired into `ai_service.warm_journey_steps()` and a read-only `GET .../steps/{id}/visual` endpoint exists — but the whole pipeline is a no-op in production today because `VISUAL_INTELLIGENCE_ENABLED=False` by default (see §2). No behavior change, no new AI spend, until that flag (and `VISUAL_NATIVE_RENDER_ENABLED`) are explicitly turned on.

## Implementation status (2026-08-30)

| Item | Status | Notes |
|---|---|---|
| Migration `010_visual_intelligence_foundation.sql` | ✅ written, ⏳ not applied | `visual_learning_objects` + `visual_plans` only, per §5 scope |
| `app/models/visual_schemas.py` | ✅ done | `VisualPlan`, `VisualStrategy`, `VISUAL_PATTERNS`, `visual_plan_text_only()` |
| Feature flags (`app/core/config.py`) | ✅ done | All 6 default `False`, per §2/§6 Q1 |
| `visual_planner` in `provider_service.DEFAULT_CONFIG` | ✅ done | `openai` / `gpt-4.1-nano`, per §6 Q2 |
| `app/services/visual_planner_service.py` | ✅ done | System prompt verbatim from spec §8; validates via `VisualPlan`; any failure degrades to text-only, never raises |
| `app/services/visual_registry_service.py` | ✅ done | SHA-256 cache-key hashing, exact-match VLO lookup, plan upsert |
| `app/services/visual_router_service.py` | ✅ done | Pure function, flag-gated per capability |
| `app/services/visual_orchestrator_service.py` | ✅ done | Ties it together; short-circuits with zero AI calls while `VISUAL_INTELLIGENCE_ENABLED=False` |
| Tests | ✅ done | `tests/unit/test_visual_planner.py`, `test_visual_router.py`, `test_visual_registry.py` — 29 tests, all passing |
| Regression check | ✅ done | Full backend suite: 439 passed, 1 pre-existing unrelated failure (`TestChatStream::test_custom_interaction_type_passed_to_stream_chat`, flagged in `plans/journey-images/README.md` before this work started), 8 skipped. Updated `tests/unit/test_usage_history.py`'s `KNOWN_INTERACTION_TYPES` guard-rail set to include `visual_planner`. |
| Wiring into `explore.py` / `warm_journey_steps()` | ❌ deliberately deferred | Per §2 — no renderer exists yet to route to |

**Remaining before this is "live" in any observable way:** flip `VISUAL_INTELLIGENCE_ENABLED` + `VISUAL_NATIVE_RENDER_ENABLED`, and build the frontend renderer components (documented, not implemented, in `frontend-changes.md`).

## Phase 2 — native renderer recipe schemas + orchestrator wiring (implemented 2026-08-30)

| Item | Status | Notes |
|---|---|---|
| `app/models/visual_recipe_schemas.py` | ✅ done | Pydantic recipe schema for all 10 patterns (spec §10-12) + `validate_recipe(pattern, dict)`. Guardrails: hierarchy max depth 4, quantity_comparison rejects negative values, node/label count bounds per pattern. |
| `app/services/visual_recipe_service.py` | ✅ done | Second cheap LLM call (`visual_recipe` interaction type, `gpt-4.1-mini`) that turns a chosen pattern + step content into a validated recipe. Returns `None` (never raises) on any failure. |
| `visual_registry_service.create_active_vlo()` | ✅ done | Inserts a new VLO as `status='active'` immediately — v1 has no async render/validate step since the recipe is already schema-validated before this is called. Idempotent via the identity unique index. |
| `visual_orchestrator_service.plan_visual_for_step()` | ✅ updated | On `NATIVE_RENDER`, now actually generates + persists the recipe and creates the VLO; downgrades to `TEXT_ONLY` if recipe generation/validation fails, rather than leaving a dangling strategy with nothing to render. |
| Wired into `ai_service.warm_journey_steps()` | ✅ done | One call after `upsert_step_content()`, inside the existing per-step try/except — same background-task context hero images use. **Not** added to the on-demand cache-miss path (`journeys.py::get_step_content`) — that's a synchronous, budget-gated request path per learner, and spec §3 explicitly says not to block it on generation; the pre-warm path already covers the overwhelming majority of step opens. |
| `GET /api/v1/journeys/{id}/steps/{id}/visual` | ✅ done | Read-only (spec §13, adapted to step-scoped addressing). Never triggers planning — returns `pending`/`unavailable`/`ready`. |
| Tests | ✅ done | `test_visual_recipe_schemas.py`, `test_visual_recipe_service.py`, `test_visual_orchestrator.py`, `tests/api/test_visual_endpoint.py` — 32 new tests. Full suite: 471 passed, 1 pre-existing unrelated failure, 8 skipped. |
| Frontend contract | ✅ documented, not implemented | `frontend-changes.md` — endpoint shape, all 10 recipe shapes, renderer registry pattern, a11y notes. |

**Deliberately not done in Phase 2:** actual renderer UI (frontend, per standing convention); `visual_assets`/`visual_jobs`/`visual_events` tables (Phases 5/6/4); retrieval, image generation, video generation (all still flag-gated off, no execution code exists for them yet); VLO reuse across steps hasn't been exercised against real traffic since the flags are off.

## Phases 3-7 + frontend (implemented 2026-08-30)

At your direction this round covered the rest of the roadmap in one pass, **including frontend implementation** — a deliberate, explicit exception to the standing "document, don't implement" frontend convention for this feature only.

### Phase 3 — versioned VLO reuse

`visual_registry_service.find_reusable_vlo()` now takes `min_version` and `create_active_vlo()` takes `version` (both default `1`). The orchestrator passes `visual_recipe_service.RECIPE_PROMPT_VERSION` for both — bumping that constant makes older VLOs invisible to reuse without deleting them (lazy regeneration, same pattern as `ai_service.CONTENT_PROMPT_VERSION`). Added `set_effectiveness_score()` for Phase 4 to write into.

### Phase 4 — telemetry

- `migrations/011_visual_events.sql` (applied) — `visual_events` table, spec §22's 7 event types.
- `app/services/visual_telemetry_service.py` — `record_event()`, `vlo_effectiveness_snapshot()` (spec §23's provisional formula, minus `quiz_improvement` which needs a join against quiz results this pass didn't build), `refresh_effectiveness_score()`.
- `POST /api/v1/journeys/{id}/steps/{id}/visual/events` — best-effort, returns `{"status": "disabled"}` while `VISUAL_TELEMETRY_ENABLED=False` (default) so the frontend can call it unconditionally without checking the flag itself.

### Phase 5 — retrieval (live: Wikimedia Commons, 2026-08-31)

`app/services/visual_retrieval_service.py` ships `VisualSourceAdapter`, `LicenseMetadata`, and `license_confidence_ok()` per spec §20-21. `SOURCE_ADAPTERS` now registers `wikimedia_commons` (`app/services/wikimedia_retrieval_adapter.py`) — the source reviewed against spec §20's "no source until licensing is reviewed" requirement: Commons requires every upload to carry machine-readable license metadata, the public search API needs no key, and `license_confidence_ok()` still gates every individual candidate image (an unrecognized or non-commercial license — e.g. any `CC BY-NC*` variant — is excluded per-image, not just per-source). `migrations/012_visual_assets.sql` (applied) is the shared `visual_assets` table this and Phase 6 both attach to.

**Content-safety gate (not in the original spec, added here deliberately):** Wikimedia Commons has no equivalent of Google's SafeSearch — it's open, user-uploaded media. Since ECALT serves a `kids` age band, `visual_orchestrator_service._try_retrieval()` only calls retrieval when `grade_band == "adults"`; `kids`/`teens`/`all` steps fall through to native-render-or-text-only regardless of `VISUAL_RETRIEVAL_ENABLED`. **Do not widen this gate without adding real content moderation first** — this was a judgment call made on your behalf, flagged for your awareness, not something the spec dictated.

### Phase 6 — image generation gateway

`app/services/visual_image_service.py` is modeled directly on the existing `image_service.py` (hero images): same OpenAI client, same `check_budget`/`record_image_usage` pattern, uploads to a **new** `visual-assets` Supabase Storage bucket keyed by content hash (so identical descriptions reuse the same object). **Operational note: the `visual-assets` bucket needs to be created manually in Supabase Storage before `VISUAL_IMAGE_GENERATION_ENABLED` is turned on** — same one-time setup `journey-images` needed (see `plans/journey-images/README.md`).

### Phase 7 — video (deliberately NOT implemented)

Per spec §30, Phase 7 shouldn't be built until Phases 2-6 produce data showing real demand for motion. `app/services/visual_video_service.py` ships only the `VideoGenerationProvider` interface (spec §18) with an empty registry — `generate_step_video()` always returns `None`. Once telemetry has run long enough to answer "how often is `generated_video` actually the recommended modality, and how much of that is already covered by `progressive_sequence`/native animation", that data should drive whether Phase 7 gets built at all.

### Orchestrator: fallback chain

`visual_orchestrator_service.py` now walks the router's chosen strategy forward through `NATIVE_RENDER -> RETRIEVE_LICENSED_ASSET -> GENERATE_IMAGE -> GENERATE_VIDEO` on execution failure (not just routing choice) — e.g. a failed recipe generation now tries retrieval/generation before giving up to `TEXT_ONLY`, matching spec §27 ("retrieval failure -> try next strategy"). Each `_try_*` helper re-checks its own flag, so this is safe even with everything still disabled by default. `plan_visual_for_step()` gained a `uid` parameter (threaded from `warm_journey_steps`) so image generation can budget-check against the right user.

### Frontend (implemented — exception to the doc-only convention, per explicit instruction)

- `lib/types.ts` — `StepVisualResponse` + all 10 recipe TS types, mirroring the backend Pydantic schemas exactly.
- `lib/api.ts` — `getStepVisual()`, `postVisualEvent()`.
- `lib/useReducedMotion.ts` — `prefers-reduced-motion` hook, used by `ProgressiveSequenceRenderer` to disable autoplay.
- `components/visual/` — `shared.tsx` (card chrome matching `StepDiagram.tsx`'s existing style), `telemetry.ts` (per-tab session id + best-effort event emission), `VisualLearningObject.tsx` (registry + runtime — renders nothing for an unrecognized `renderer_type`, never uses `dangerouslySetInnerHTML` since recipes are typed data, not markup), and `renderers/` with all 10 pattern components (`ProcessFlowRenderer`, `CycleRenderer`, `CauseEffectRenderer`, `ComparisonRenderer`, `TimelineRenderer`, `HierarchyRenderer`, `PartToWholeRenderer`, `BeforeAfterRenderer`, `QuantityComparisonRenderer`, `ProgressiveSequenceRenderer`).
- `StepNode.tsx` — after step content loads, best-effort fetches the step's visual (`getStepVisual`, swallows errors) and renders `<VisualLearningObject>` beneath the content when `status === 'ready'`.
- Verified: `tsc --noEmit` clean, `vite build` succeeds, dev server boots and serves 200 with no console errors at import time.
- **Known gap:** `GET .../visual` requires auth (`get_acting_uid`, no guest path) — unauthenticated guests never see a visual (silently, via the `.catch(() => {})` in `StepNode`). Matches how quizzes are already guest-gated in this app; not fixed here since it wasn't flagged as a requirement.
- **`ImageRenderer` added (2026-08-30, later same day):** covers `RETRIEVE_LICENSED_ASSET`/`GENERATE_IMAGE` results. This required a backend fix first — `visual_registry_service.get_step_visual()` was joining `visual_learning_objects` but never `visual_assets`, so an asset-backed VLO had no way to reach the frontend at all (`renderer_type`/`recipe` are empty for those strategies; the actual image lives in `visual_assets.external_url`). Fixed with a `LEFT JOIN LATERAL` for the most recent `status='active'` asset, and `StepVisualResponse` gained `asset_url`/`asset_type`/`attribution`/`license_type`. `VisualLearningObject.tsx` now dispatches to `ImageRenderer` when `asset_url` is present instead of `renderer_type`/`recipe`; renders an `<img>` (or `<video>` for forward-compat, though nothing produces one until Phase 7) with an attribution line shown only for non-generated (i.e. retrieved/licensed) assets. `GENERATE_VIDEO` still has no UI and no backend execution — unaffected.

### How to turn this on (all still off by default)

1. `VISUAL_INTELLIGENCE_ENABLED=true` + `VISUAL_NATIVE_RENDER_ENABLED=true` — the safe first step, native diagrams only, no external spend beyond the two cheap LLM calls (planner + recipe) per step.
2. `VISUAL_IMAGE_GENERATION_ENABLED=true` — only after creating the `visual-assets` Storage bucket and adding an `<img>` renderer for `generated_image`/`retrieved_image` modality (see gap above).
3. `VISUAL_RETRIEVAL_ENABLED=true` — functional now (Wikimedia Commons is registered), but only affects `adults`-grade-band steps by design (content-safety gate, see Phase 5 above). Verify the `visual-assets` Supabase Storage bucket is set **public**, not just created — `visual_image_service.upload_visual_image()`'s returned URLs assume public read access, same as the existing `journey-images` bucket.
4. `VISUAL_TELEMETRY_ENABLED=true` — safe any time; frontend already calls the endpoint unconditionally.
5. `VISUAL_VIDEO_GENERATION_ENABLED` — leave off; no provider exists (Phase 7).

### Full test count

Backend: 519 passed, 1 pre-existing unrelated failure, 8 skipped. Frontend: `tsc --noEmit` and `vite build` both clean; no automated frontend test suite exists in this repo to extend.

### Live in production (2026-08-31) — confirmed via direct DB query

Verified against the real prod Supabase DB after your Railway flag flips: `visual_plans` has real `NATIVE_RENDER`/`NONE`/`TEXT_ONLY` rows from actual journey generation, `process_flow` and `part_to_whole` renderers have both fired. Found and fixed a real bug from this: `flex-wrap` on the native diagram node rows let an arrow strand itself at a line-wrap point, pointing at nothing (seen live on an "EC2 instance lifecycle" diagram) — switched to a non-wrapping horizontally-scrollable row. `visual_events` was confirmed empty (0 rows) — `VISUAL_TELEMETRY_ENABLED` was not yet on at that check.

This doc maps the spec's generic architecture onto the actual ECALT repo, calls out where the spec's assumptions don't match reality, and lays out a phase-by-phase plan scoped to what this codebase actually needs. Per standing project convention, **frontend changes are documented here, not implemented** — a separate `frontend-changes.md` will be written once Phase 2 (renderers) is ready to review.

---

## 1. How the spec maps onto this repo

| Spec concept | ECALT reality |
|---|---|
| "Course" / "Lesson" | ECALT has **journeys** and **steps**, not courses/lessons. `journeys` table (`id text` PK), with `steps jsonb` — the full step list is embedded as a JSON array *inside* the journey row. There is no separate `steps` table. |
| "Content block" / `content_block_id` (spec §14) | **Doesn't exist.** A step's content is a single markdown blob (`step_content.content`), not a list of typed blocks. Diagrams are already embedded inline in that markdown (mermaid fences / `<svg>`) by the step-content prompt itself. **Decision: visual attachment is step-scoped for v1** — one visual plan/slot per `(journey_id, step_id)`, not per arbitrary block. This is the single biggest adaptation from the spec. |
| ORM + "database entity" | **No ORM anywhere.** Raw `psycopg2` via `app/core/database.get_db()`, flat numbered SQL migrations in root `migrations/` (currently `001`–`009`). New tables are plain SQL, and Python-side there's no model class per row — services return/consume plain dicts, matching every other service in the codebase. |
| AI provider abstraction / "ai.ts" | `app/services/provider_service.py`: `get_config(interaction_type)` (admin-editable via `ai_provider_config` table, code-side `DEFAULT_CONFIG`/`DEFAULT_STYLE_PROMPTS` fallback) + `complete_text(interaction_type, system, user_content, max_tokens)`. This is the one call every AI feature in ECALT goes through — the Visual Planner will use it exactly like `journey`/`step_content`/`quiz` do today. |
| Structured/validated LLM output | No existing Zod/Pydantic-validated structured-output helper — other services hand-parse JSON via a shared repair regex (`ai_service._loads_ai_json`, fixes LaTeX-style stray backslashes) and read dict keys directly, no schema enforcement. **The Visual Planner will be the first place with real Pydantic validation of LLM output** (`VisualPlan`, already drafted — see below). |
| Job queue (spec §17, §6.5 `visual_jobs`) | **No queue system** — no Celery/RQ/Redis anywhere in the codebase (confirmed via grep). Expensive async work (hero image generation) uses plain **FastAPI `BackgroundTasks`**, fired once after journey persist. APScheduler (`app/services/scheduler.py`) exists but is purpose-built for notification cron jobs, not a generic job runner — not a fit for visual jobs. **Decision: Phase 1 does not create a `visual_jobs` table.** When Phase 6 (generation gateway) needs async execution, it'll follow the same `BackgroundTasks` pattern `image_service.py` already uses, and a `visual_jobs` table (for retry/observability) can be added in that phase's own migration. |
| Generation provider abstraction (spec §18) + budget guardrails (§19) | **Already exists, working, in production**: `app/services/image_service.py` generates journey hero images (OpenAI `gpt-image-1-mini`), is feature-gated (`images_enabled()`), calls `subscription_service.check_budget()` / `record_image_usage()` before spending, uploads to Supabase Storage, and **never raises** — failures degrade silently to "no image". This is the exact reference implementation for spec §18/§19's `ImageGenerationProvider` + `authorizeGeneration`. Phase 6 should copy this pattern, not invent a new one. |
| Feature flags (spec §33) | Plain `bool` fields on the pydantic-settings `Settings` class in `app/core/config.py` (e.g. `SCHEDULER_ENABLED: bool = True`). No separate flag service. New `VISUAL_*` flags will follow this exact pattern. |
| `visual_embeddings` / semantic retrieval (spec §6.4) | No vector extension/pgvector usage found anywhere in the schema. Per spec §6.4 itself ("only add this when semantic retrieval is implemented") — **skipped entirely for v1**, including Phase 5. Retrieval ranking will use the "simpler deterministic ranking" the spec explicitly allows as a fallback. |
| Frontend diagram rendering | Already built: `frontend/src/components/MarkdownContent.tsx` regex-splits content on mermaid/svg blocks, `frontend/src/components/StepDiagram.tsx` renders them (client-side `mermaid.render()` with a `suppressErrors` guard, `dangerouslySetInnerHTML` for pre-sanitized SVG). A future `<VisualLearningObject>` runtime (spec §25) is a **new chunk type in that existing pipeline**, not a parallel system. **Not touched in this plan** — will be handed off as a documented frontend contract per your standing instruction. |

---

## 2. Scope decision for "Phase 1" in this repo

The spec's Phase 1 acceptance criteria (§30):
- VisualPlan schema ✅ (planned)
- VisualPlan DB table ✅ (planned)
- VisualLearningObject DB table ✅ (planned)
- VisualOrchestrator / VisualPlanner / VisualRouter ✅ (planned, standalone services)
- "existing course generation remains backward compatible"

**Important scope call:** Phase 1 as planned here builds these as **standalone, tested, callable services — not wired into `explore.py` / `warm_journey_steps()` yet.** Reasoning:
- Wiring it in now means every journey generation starts making an extra LLM call (the planner) for every step, with zero payoff — there are no renderers yet (Phase 2), so the router can only ever return `NONE` / `TEXT_ONLY` / occasionally `REUSE_VLO` if a VLO is manually seeded. That's pure added cost and latency for no learner-visible benefit.
- It keeps this PR small and independently testable, matching the spec's own instruction not to combine everything into one giant PR (§31).
- The actual integration point (one line: call the orchestrator from inside `warm_journey_steps()` in `ai_service.py`, after existing step-content generation, same `BackgroundTasks` context) is trivial to add once there's a renderer to route to — it'll happen naturally in Phase 2/3.

Corollary: `VISUAL_INTELLIGENCE_ENABLED` defaults to **`False`** here, not `True` as the spec's §33 default table suggests — because "on" currently means "makes AI calls that can never produce a visible visual." Flip it to `True` once Phase 2 lands and wiring happens. **This is a deviation from the spec worth confirming with you.**

---

## 3. What Phase 1 actually built

1. **`migrations/010_visual_intelligence_foundation.sql`** — creates `visual_learning_objects` and `visual_plans` only (not `visual_assets`/`visual_jobs`/`visual_events` — those are deferred to the phases that use them, see §5 below). Columns match spec §6.1/§6.3, adapted: `course_id`→`journey_id text REFERENCES journeys(id)`, `content_block_id` dropped (step-scoped), `lesson_id`→folded into `step_id text` (no steps table to reference). One unique index enforces "one visual slot per step" via `(journey_id, step_id)`. RLS enabled with no policy, matching the exact pattern of the most recent migration (`009_course_marketplace.sql`'s `journey_likes` table) — the backend connects via a privileged role that bypasses RLS, so existing tables don't carry explicit policies either. **Not yet applied to the DB.**
2. **`backend/app/models/visual_schemas.py`** — `VisualPlan` Pydantic model matching spec §7 exactly (all field names preserved: `visualRequired`, `conceptProperties`, `recommendedModality`, etc.), plus a `visual_plan_text_only()` graceful-degradation factory (spec §27: planner failure → no visual, never blocks the lesson) and a `VisualStrategy` literal collapsed to what Phase 1 can actually produce (`NATIVE_INTERACTIVE`/`NATIVE_ANIMATION` folded into `NATIVE_RENDER` since no renderer registry exists until Phase 2).

---

## 4. Phase 1 work (implemented)

| File | Purpose |
|---|---|
| `backend/app/core/config.py` | Add 6 flags: `VISUAL_INTELLIGENCE_ENABLED` (default `False`, see §2), `VISUAL_NATIVE_RENDER_ENABLED` (`False`), `VISUAL_RETRIEVAL_ENABLED` (`False`), `VISUAL_IMAGE_GENERATION_ENABLED` (`False`), `VISUAL_VIDEO_GENERATION_ENABLED` (`False`), `VISUAL_TELEMETRY_ENABLED` (`False`) |
| `backend/app/services/provider_service.py` | Add `"visual_planner"` to `DEFAULT_CONFIG` (proposed: `openai` / `gpt-4.1-nano` — this is a cheap structured-classification call, same tier as `nudge`/`daily_spark`, not `journey`-tier) and `DEFAULT_STYLE_PROMPTS` (the planner uses its own hardcoded system prompt per spec §8, not an admin-editable style prompt — entry can map to `""`) |
| `backend/app/services/visual_planner_service.py` (new) | `PLANNER_PROMPT_VERSION` constant; system prompt from spec §8 (verbatim, it's already ECALT-agnostic); `build_user_prompt(...)`; `async def plan_visual(context) -> VisualPlan` — calls `provider_service.complete_text("visual_planner", ...)`, reuses `ai_service._loads_ai_json` for the same backslash-repair the rest of the codebase needs, validates into `VisualPlan`; on any parse/validation failure returns `visual_plan_text_only(...)` rather than raising |
| `backend/app/services/visual_registry_service.py` (new) | Hashing helpers (`sha256`-based `concept_hash`/`objective_hash`, matching spec §15's cache-key scheme); `find_reusable_vlo(concept_key, objective_hash, grade_band, modality) -> dict \| None` (SQL lookup, `status='active'`); `upsert_visual_plan(...)` (the `ON CONFLICT (journey_id, step_id) DO UPDATE` pattern already used by `provider_service.set_config`) |
| `backend/app/services/visual_router_service.py` (new) | `select_strategy(plan: VisualPlan, existing_vlo, flags) -> VisualStrategy` — deterministic, per spec §9 pseudocode, gated by the feature flags above so every non-`NONE`/`TEXT_ONLY`/`REUSE_VLO` branch is inert until its phase lands |
| `backend/app/services/visual_orchestrator_service.py` (new) | `async def plan_visual_for_step(journey, step, learner_context) -> dict` — ties planner → hash → registry lookup → router → persist together; short-circuits immediately (no AI call) if `settings.VISUAL_INTELLIGENCE_ENABLED` is `False`; wraps everything in try/except so a failure here can **never** affect journey/step generation (spec §27) |
| `backend/tests/unit/test_visual_planner.py`, `test_visual_router.py`, `test_visual_registry.py` (new) | Schema validation, router decision-tree cases (including a few of the spec §32 golden fixtures — photosynthesis, water cycle — as router-only fixtures since no LLM call in unit tests), cache-key determinism |

**Explicitly not in Phase 1:** no call site added in `explore.py` or `ai_service.warm_journey_steps()` (see §2); no renderers; no `visual_assets`/`visual_jobs`/`visual_events` tables; no frontend changes.

---

## 5. Full phase roadmap (for context — not being implemented now)

| Phase | Scope | New migration |
|---|---|---|
| 1 (this doc) | Schemas, VLO+plan tables, planner, router, orchestrator (standalone) | `010_visual_intelligence_foundation.sql` |
| 2 | `process_flow`, `comparison`, `progressive_sequence` renderers (recipe schema + validation, **backend only** — actual rendering is React, documented not implemented per your frontend policy); wire orchestrator into `warm_journey_steps()`; flip `VISUAL_INTELLIGENCE_ENABLED`/`VISUAL_NATIVE_RENDER_ENABLED` | `011_visual_renderer_registry.sql` (if renderer metadata needs persisting) |
| 2b | Remaining 7 renderers | — |
| 3 | VLO reuse hardening, versioning on renderer/recipe-schema change | — |
| 4 | Telemetry: `visual_events` table + emission | `01x_visual_events.sql` |
| 5 | Retrieval: source adapters, license policy, `visual_assets` table | `01x_visual_assets.sql` |
| 6 | Generation gateway (image first, modeled on `image_service.py`), budget authorization, `visual_jobs` table | `01x_visual_jobs.sql` |
| 7 | Video — only after Phase 2-6 data shows real demand (spec explicitly defers this) | — |

Each phase gets its own PR, migration (only when that phase needs new tables), and test suite — no combined mega-PR, per spec §31.

---

## 6. Open questions for you

1. **Flag defaults** — confirm `VISUAL_INTELLIGENCE_ENABLED=False` for now (§2), overriding the spec's suggested `True`, since nothing can render a visual until Phase 2.
2. **Model for `visual_planner`** — proposed `gpt-4.1-nano` (cheapest tier, same as `nudge`/`daily_spark`). This runs once per step if/when wired in Phase 2 — at ~$0.01/1M input tokens it's negligible, but worth confirming since it decides on every future visual.
3. **`001_security_hardening.sql`** is currently untracked in git (per `git status`) — before this PR lands, worth confirming that migration has actually been applied to prod, since `010` will be the next one applied after it.
4. Does "Phase 1 now, standalone" match your expectations, or would you rather I wire the orchestrator into `warm_journey_steps()` immediately (behind the flag) even though it can't produce a visible visual yet?

Once you sign off, I'll implement exactly what's in §4, run the backend test suite, and report the diff — nothing further until then.
