# Visual Intelligence Layer — Frontend Changes

**Status: implemented 2026-08-30**, by explicit instruction — a one-time exception to the standing "document, don't implement" frontend convention. `tsc --noEmit` and `vite build` both pass; dev server verified to boot cleanly. Still dormant in production: `VISUAL_INTELLIGENCE_ENABLED=False` by default, so the API described below currently always returns `{"status": "pending"}` — there is no live data to render yet, and nothing in this doc affects the app until the backend flags are turned on (see `README.md`'s "How to turn this on"). The original pre-implementation spec is kept below as the reference for what was built and why.

## New endpoint

`GET /api/v1/journeys/{journey_id}/steps/{step_id}/visual` (auth required, same as `.../content`). Read-only — never triggers planning or generation.

Response (`StepVisualResponse`):

```ts
type StepVisualResponse = {
  journey_id: string;
  step_id: string;
  status: "pending" | "unavailable" | "ready";
  strategy?: "NONE" | "REUSE_VLO" | "NATIVE_RENDER" | "RETRIEVE_LICENSED_ASSET" | "GENERATE_IMAGE" | "GENERATE_VIDEO" | "TEXT_ONLY";
  modality?: string;                 // e.g. "native_diagram", "animated_process"
  renderer_type?: string;            // one of the 10 pattern names below, when status === "ready"
  recipe?: Record<string, unknown>;  // pattern-specific shape, see below
  pedagogical_role?: string;         // "hook" | "anchor" | "explain" | "compare" | "demonstrate" | "simulate" | "practice" | "recap"
};
```

- `status: "pending"` — no plan exists yet for this step (content generation hasn't reached it, or the feature is disabled). Treat exactly like `hero_image_url: null` in the journey-images work: render nothing, no skeleton loader needed for v1.
- `status: "unavailable"` — a plan was made and no visual was warranted (or generation failed and degraded to text). Render nothing.
- `status: "ready"` — `renderer_type` + `recipe` are populated and validated server-side. Safe to render.

Suggested integration point: call this alongside (or right after) the existing `GET .../content` call when a learner opens a step, same pattern as the step-content fetch.

## Renderer components needed (once `status === "ready"` starts showing up)

A registry keyed by `renderer_type`, conceptually per spec §25:

```ts
const rendererRegistry: Record<string, React.ComponentType<{ recipe: any }>> = {
  process_flow: ProcessFlowRenderer,
  cycle: CycleRenderer,
  cause_effect: CauseEffectRenderer,
  comparison: ComparisonRenderer,
  timeline: TimelineRenderer,
  hierarchy: HierarchyRenderer,
  part_to_whole: PartToWholeRenderer,
  before_after: BeforeAfterRenderer,
  quantity_comparison: QuantityComparisonRenderer,
  progressive_sequence: ProgressiveSequenceRenderer,
};
```

A `<VisualLearningObject stepVisual={data} />` wrapper picks the component by `renderer_type`, and:
- renders nothing (not an error state) if `renderer_type` is missing from the registry — forward-compat with server-side patterns the frontend hasn't shipped a renderer for yet;
- respects `prefers-reduced-motion` for anything with `progressiveReveal`/`looping`/`autoPlay`;
- never executes anything from `recipe` as code/HTML — it's typed data only (labels, ids, roles), safe to interpolate as text content. No `dangerouslySetInnerHTML` needed anywhere in this pipeline, unlike the existing mermaid/SVG diagram path.

### Exact recipe shapes (backend-validated, see `app/models/visual_recipe_schemas.py`)

- **process_flow**: `{title, nodes: [{id, label, role: "input"|"process"|"output"}], connections: [{from, to}], progressiveReveal}`
- **cycle**: `{title, nodes: [{id, label}] (3-8), connections: [{from, to}], progressiveReveal, looping}`
- **cause_effect**: `{title, nodes: [{id, label, role: "cause"|"mechanism"|"effect"}], connections: [{from, to}]}`
- **comparison**: `{title, columns: [{id, label, items: string[]}] (2-3 columns)}` — stack vertically on mobile
- **timeline**: `{title, events: [{id, label, when}], progressiveReveal}`
- **hierarchy**: `{title, nodes: [{id, label, parentId}]}` — tree layout, max depth 4 (server-enforced)
- **part_to_whole**: `{title, whole, parts: [{id, label, description?}]}` — click/tap a part to show its description
- **before_after**: `{title, before: {label, description}, after: {label, description}}`
- **quantity_comparison**: `{title, items: [{id, label, value, unit?}]}` — values are always ≥0 (server-enforced); scale bars/areas linearly, don't truncate the axis
- **progressive_sequence**: `{title, steps: [{id, label, content}], autoPlay}` — needs next/previous/replay controls; disable `autoPlay` when `prefers-reduced-motion` is set regardless of the flag's value

## Accessibility (spec §24, carries over from the existing diagram work)

Every renderer needs an `alt`/text-equivalent description (the `recipe.title` plus a generated summary of nodes/labels is enough for v1 — don't rely on color alone to convey the `role`/type distinctions, use shape or a text label too).

## Out of scope for this doc

Retrieval-based images/video (`RETRIEVE_LICENSED_ASSET`, `GENERATE_IMAGE`, `GENERATE_VIDEO` strategies) have no backend implementation yet (Phases 5-6) — `status` will never be `"ready"` with those strategies today. No frontend work needed for them until those phases land.
