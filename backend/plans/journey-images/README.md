# Journey Images Plan — Visuals for Generated Courses

**Goal:** Generate images alongside AI-generated course content — for both the explore flow (`POST /explore`, `/explore/preview` + `/confirm`) and journey step content (`GET /journeys/{id}/steps/{id}/content`) — without blowing up latency or the per-user token budget.

**Status:** Drafted 2026-07-18. Phases 0–2 implemented 2026-07-18 (uncommitted).

## Implementation status (2026-07-18)

| Phase | Status | Notes |
|---|---|---|
| 0 Infra | ✅ done | `journey_image` in `DEFAULT_CONFIG` (gpt-image-1-mini), `COST_PER_IMAGE` + `cost_for_images`, `record_image_usage`; migration `008_journey_images.sql` **applied to prod** (`journeys.hero_image_url`, `step_content.image_url`, public `journey-images` bucket); `SUPABASE_URL` set in `.env` — **`SUPABASE_SERVICE_ROLE_KEY` still needs a value (dashboard > Settings > API) + both vars in Railway** |
| 1 SVG/mermaid diagrams | ✅ done | Diagram rules in `_STEP_CONTENT_CONTRACT` (code-side, no DB prompt write needed); `sanitize_step_diagrams` allowlist sanitizer; `CONTENT_PROMPT_VERSION` 2→3 (cached steps lazily regenerate); step max_tokens 3200→3600. Critic extension deferred — sanitizer covers broken SVG, mermaid fails soft client-side |
| 2 Hero images | ✅ done | `image_service.py` (generate → WebP → Supabase Storage via httpx, budget-checked, never raises); hooks: explore confirm + legacy, recommendations gap-fill, generated next-level; `Journey.hero_image_url` in schema + `_row_to_journey`; admin `POST /admin/journeys/{id}/hero-image/regenerate`; `scripts/generate_curated_heroes.py` (not yet run — needs service key) |
| 3 Per-step images | ⏳ deferred | on-demand / paid-tier, per plan |
| 4 Frontend | ✅ done | Hero on `JourneyCard` + journey hero card (async refetch); mermaid/SVG rendering in `MarkdownContent` via `StepDiagram.tsx` (mermaid npm dep, lazy chunk). Details in `frontend-changes.md` |

Tests: `tests/unit/test_journey_images.py` (15 tests); suite green except pre-existing `TestChatStream::test_custom_interaction_type_passed_to_stream_chat`. Volume check (prod, last 60d): 77 journeys → ~40/mo → **~$0.35/mo** at gpt-image-1-mini.

Remaining to go live: set `SUPABASE_SERVICE_ROLE_KEY` locally + both vars in Railway; run `scripts/generate_curated_heroes.py` and paste URLs into `SAMPLE_JOURNEYS`; deploy; verify one real journey end-to-end.

---

## Current state (what exists today)

| Thing | Where | Notes |
|---|---|---|
| Journey skeleton generation | `generate_journey()` — `ai_service.py:495` | gpt-4.1, returns title/description/steps/tags + an **emoji `icon`** (the only "visual" today) |
| Step content generation | `generate_step_content()` — `ai_service.py:167` | gpt-4.1-mini, markdown `content` + `quiz_anchors`, cached in `step_content` table, warmed sequentially by `warm_journey_steps()` after confirm |
| Cost tracking | `cost_for_tokens()` — `provider_service.py:732`, `record_usage()` — `subscription_service.py:217` | **cents, per token** — no concept of per-image cost |
| Budget gate | `check_budget()` — free plan default ≈ **20¢/month** (`token_budget_cents`) | every generation path checks it first |
| Model/prompt config | `ai_provider_config` (Supabase) via `provider_service.get_config()` | prod truth is the DB row, not code |
| Image storage | **None.** `app/core/supabase.py` exists but is dead code: `supabase` is not in `requirements.txt` and `SUPABASE_URL`/`SUPABASE_KEY` are not in `Settings` (`config.py`) | must be built |
| Curated journeys | Hardcoded `SAMPLE_JOURNEYS` in `journeys.py:30` | can be given pre-generated, hardcoded image URLs (one-time cost) |

Key constraint: content is stored as **markdown text in Postgres**. Images therefore need object storage + a URL referenced from the row (or embedded as markdown `![](url)`).

---

## Yes, it's possible — three ways to add visuals, ranked by cost-effectiveness

### Option A — LLM-drawn SVG / Mermaid diagrams inside step content (near-zero cost) ⭐ do this first
The step-content model (gpt-4.1-mini) can emit an inline `<svg>` or ```mermaid block as part of the markdown it already produces. For *educational* content, a labeled diagram (DNA ladder, force arrows on a rocket, a supply/demand curve) teaches better than a decorative AI photo.

- **Cost:** ~500–900 extra output tokens per step on gpt-4.1-mini ≈ **0.08–0.15¢ per step** (vs ~0.45¢ the step already costs). Effectively free.
- **No storage, no new infra, no latency hit** (same completion call), renders client-side, scales to any resolution, dark-mode friendly.
- **Risk:** mini-model SVGs can be malformed/ugly → constrain to a small set of diagram archetypes in the prompt + fall back to no-diagram on validation failure.

### Option B — One AI-generated hero image per journey (small, bounded cost)
Generate a single cover/hero image at journey creation (explore confirm), from title + description + tags with a fixed house style. Cache forever in object storage; every viewer shares it.

- **Cost:** ~0.2–4¢ **per journey, once** depending on model (table below).
- Replaces the emoji `icon` as the card visual; big perceived-quality win for the explore result page and journey cards.

### Option C — AI-generated raster image per step (expensive — gate it)
1 image × ~7 steps at decent quality = **8–30¢ per journey** — that alone exceeds the free plan's entire 20¢ monthly budget and is ~5× the cost of all the text in the journey. Only viable for paid plans, cheap models, or "generate on request" (a button per step, budget-checked like regenerate).

**Recommendation: A + B now; C later as a paid-tier/on-demand feature.**

---

## Cost implications

### Image model options (per 1024×1024 image; verify current pricing before Phase 0 exit)

| Model / source | ~$/image | ¢/image | Notes |
|---|---|---|---|
| OpenAI `gpt-image-1-mini` (low/med) | $0.005–0.011 | 0.5–1.1¢ | cheapest OpenAI path, same SDK we already use |
| OpenAI `gpt-image-1` low | $0.011 | 1.1¢ | good enough for card-size heroes |
| OpenAI `gpt-image-1` medium | $0.042 | 4.2¢ | noticeably better; = 20% of a free budget |
| OpenAI DALL·E 3 standard | $0.040 | 4¢ | legacy; prefer gpt-image-1 |
| Google Gemini 2.5 Flash Image | $0.039 | 3.9¢ | new provider integration needed |
| Flux schnell (fal.ai / Replicate) | ~$0.003 | 0.3¢ | cheapest overall; new provider + API key |
| Stock (Unsplash/Pexels API) | $0 | 0¢ | free but weak topical relevance for abstract concepts; attribution UX |

### Per-journey cost: today vs with images (7-step journey, current prod models)

| Item | Cost |
|---|---|
| Journey skeleton (gpt-4.1, ~1k in / 2.5k out) | ~2.2¢ |
| 7 steps warmed (gpt-4.1-mini, ~1.5k in / 2.5k out each) + nano critic | ~3.3¢ |
| **Text total today** | **~5.5¢** |
| + Option A: SVG diagrams in all 7 steps | +~0.8¢ (**+15%**) |
| + Option B: 1 hero, gpt-image-1-mini | +~1¢ (**+18%**) |
| + Option B: 1 hero, gpt-image-1 medium | +~4.2¢ (**+76%**) |
| + Option C: 7 step images, gpt-image-1 low | +~7.7¢ (**+140%**) |
| + Option C: 7 step images, gpt-image-1 medium | +~29¢ (**+530%, exceeds free budget alone**) |

### Monthly projection (formula: journeys/month × per-journey image cost)

| Volume | A+B (mini hero) | A+B (medium hero) | A+B+C (medium, per step) |
|---|---|---|---|
| 100 journeys/mo | ~$1.80 | ~$5 | ~$34 |
| 500 journeys/mo | ~$9 | ~$26 | ~$168 |
| 2,000 journeys/mo | ~$36 | ~$104 | ~$670 |

Pull actual last-30-day journey volume from `usage_by_interaction` before committing (Phase 0).

### Storage / bandwidth (Supabase Storage)
- ~150–300KB per compressed WebP hero → 5,000 images ≈ 1–1.5GB stored ≈ **pennies/month** ($0.021/GB).
- Egress is the real variable: heroes are viewed by many users. Serve via Supabase CDN with long-lived `Cache-Control`; watch plan egress quota (free tier 5GB/mo, Pro 250GB/mo). At 200KB × 50k views/mo ≈ 10GB/mo — fine on Pro, over free-tier limit.

### Budget accounting
Images must debit the same `token_usage.estimated_cost_cents` pool or paid users get uncapped spend. Add a `COST_PER_IMAGE` table (cents/image by model+quality) in `provider_service.py` and a `record_image_usage(uid, model, n)` beside `record_usage()`. Free plan keeps hero images only if headroom exists (1¢ of a 20¢ budget is fine; 4.2¢ is a product call — consider hero images only for paid plans, or bump `token_budget_cents`).

---

## Phase 0 — Decisions + infra (½–1 day)

1. **Pick the hero model** (recommend `gpt-image-1-mini` or `gpt-image-1` low — existing OpenAI SDK, no new provider) and **verify current pricing**; record it in `COST_PER_IMAGE`.
2. **Storage:** create Supabase Storage bucket `journey-images` (public read). Talk to it with plain `httpx` REST (`POST {SUPABASE_URL}/storage/v1/object/journey-images/...` with service-role key) — avoids adding the `supabase` package. Add `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` to `Settings` (this also fixes the dead `app/core/supabase.py` — either wire it or delete it).
3. **Config:** add `interaction_type="journey_image"` to `DEFAULT_CONFIGS` in `provider_service.py` so model/quality is admin-switchable via `ai_provider_config` like everything else. Remember: **prod behavior = DB row, not code.**
4. **Migration:** `journeys.hero_image_url TEXT NULL`; `step_content.image_url TEXT NULL` (for Phase 3). Old rows just render the emoji icon as before.
5. Pull real journey/step volume for the last 30 days → plug into the projection table above; get the spend approved.

**Exit criteria:** bucket exists, env vars in Railway, migration applied, cost table verified against live pricing pages, projected monthly delta signed off.

---

## Phase 1 — SVG/Mermaid diagrams in step content (1–2 days, Option A)

1. Extend `_STEP_CONTENT_CONTRACT` (`ai_service.py`): for `concept`/`practice` steps, allow one optional ```mermaid block **or** one inline `<svg>` (viewBox, max ~40 elements, no external refs, no `<script>`/`<foreignObject>`) at the point in the lesson where it aids understanding. Give 2–3 archetypes (flow, labeled parts, comparison) with a contrast few-shot.
2. **Sanitize server-side:** strip/reject any SVG containing `script`, event handlers (`on*=`), external `href`/`xlink` — it's rendered in users' browsers. Reject → serve content without the diagram (fail open, like the critic).
3. Bump `CONTENT_PROMPT_VERSION` so existing cached steps lazily regenerate with diagrams via the existing background-refresh path (`journeys.py:711`).
4. Extend the content critic to flag broken/degenerate diagrams.

**Exit criteria:** ≥70% of new concept steps carry a valid diagram; zero unsanitized SVG reaches the DB; token cost delta ≈ +0.1¢/step confirmed in `usage_by_interaction`.

---

## Phase 2 — Journey hero image (2–3 days, Option B)

1. **`app/services/image_service.py`:**
   - `generate_hero_image(journey) -> bytes`: prompt built from a **fixed house-style template** + journey title/description/tags. Kid-safe by construction: the user's raw question never goes into the image prompt — only the model-generated title/tags, plus style rules ("friendly flat educational illustration, no text, no people's likenesses"). Respect `age_group` (the parental `content_age_band` override in `explore.py:19` already shapes it upstream).
   - `upload_journey_image(journey_id, bytes) -> url`: compress to WebP (~1024px), upload to `journey-images/{journey_id}.webp`, long-lived cache headers, return public URL.
2. **Hook into both persist paths** (`/explore/confirm` and legacy `POST /explore`) as a **background task alongside `warm_journey_steps`** — image generation takes 5–20s and must never block the response. On success, `UPDATE journeys SET hero_image_url = ...`. Also hook the recommendation gap-fill persist (`journeys.py:400`) and `generate_next_level`.
3. **Budget:** `check_budget(uid)` before generating; `record_image_usage()` after. Failure = journey simply has no image (emoji fallback) — never fail the journey.
4. `Journey` schema: add `hero_image_url: Optional[str]`; populate in `_row_to_journey`. Curated `SAMPLE_JOURNEYS`: generate once with a script, upload, hardcode URLs.
5. Regeneration/moderation hatch: admin-only `POST /admin/journeys/{id}/hero-image/regenerate`.

**Exit criteria:** new journeys get a hero within ~30s of confirm; free-plan cost impact ≤ ~1¢/journey (or gated to paid — product call from Phase 0); explore result + journey cards show images (frontend doc, see below).

---

## Phase 3 — Per-step images, on demand (later, Option C — only if wanted)

Not cost-viable as a default (see table). If pursued:
- **On-request button** per step ("Illustrate this") → `POST /journeys/{id}/steps/{id}/image`, budget-checked + rate-limited (mirror `regenerate_step_content`, `10/hour`), cached in `step_content.image_url` so later viewers get it free.
- Or auto-generate for **paid plans only**, one image per journey's first concept step, cheapest quality.
- Prompt seed: the step's `core_question` + `seed_facts` (already in the steps jsonb) make much better image prompts than the 120-char description.

**Exit criteria:** per-plan gating enforced in `check_budget` context; image spend visible per interaction_type in `usage_by_interaction`.

---

## Phase 4 — Frontend documentation (convention: document, don't implement)

Per project convention, frontend work ships as a spec md — write `frontend-changes.md` in this folder covering:
- Journey card + explore preview: render `hero_image_url` with emoji-icon fallback (skeleton shimmer while null; poll or refetch after confirm since the image lands async).
- Step content: render fenced ```mermaid blocks (mermaid.js) and inline SVG from trusted-API markdown; sanitizer allowlist must permit `svg` from our API only.
- Optional "Illustrate this" button (Phase 3).

---

## Safety & quality notes (kids' product)

- Fixed style template + no raw user text in image prompts (title/tags are already model-generated and topic-scoped by `check_topic_scope`).
- OpenAI image endpoints run their own content moderation; on moderation refusal, fall back silently to emoji icon.
- "No text in image" instruction — image models render garbled text, and it breaks localization.
- SVG sanitization is a hard security requirement (Phase 1.2), not a nice-to-have.

## Rollout order & rollback

| Phase | Risk | Rollback |
|---|---|---|
| 1 (SVG) | Malformed diagrams | Prompt-version revert via `ai_provider_config`; sanitizer fails open to text-only |
| 2 (hero) | Cost, latency | Background-only, budget-gated; kill switch = disable `journey_image` config row; UI falls back to emoji |
| 3 (step images) | Cost | On-demand + rate-limited + plan-gated by design |

Key files:
- `app/services/ai_service.py` — step contract, prompt version, warm task
- `app/services/provider_service.py` — `DEFAULT_CONFIGS`, `COST_PER_IMAGE` (new), config plumbing
- `app/services/image_service.py` — **new**: generation + upload
- `app/services/subscription_service.py` — `record_image_usage` (new), budget gate
- `app/api/v1/endpoints/explore.py`, `journeys.py` — background hooks, schema exposure
- `app/core/config.py` — `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `ai_provider_config` (Supabase) — prod truth for the image model/quality
