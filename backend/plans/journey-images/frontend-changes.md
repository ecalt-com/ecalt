# Journey Images — Frontend Changes

**Status: implemented 2026-07-18.** Hero images render on `JourneyCard` (16:9
header, emoji fallback) and as a background wash on the `Journey.tsx` hero card
(with a one-shot 15s refetch for journeys <2min old); diagrams render via
`MarkdownContent` → `StepDiagram.tsx` (mermaid lazy-loaded with
`securityLevel: 'strict'`, dark-mode theme; server-sanitized SVG in a white
panel). CSP already allowed `img-src https:` — no `vercel.json` change.
Original spec below.

---

Backend is live-ready (see README status). Two independent frontend pieces:

## 1. Hero images on journey cards + explore result

**API change:** `Journey` objects now include `hero_image_url: string | null` — on
`GET /journeys`, `GET /journeys/{id}`, `POST /explore`, `/explore/confirm`,
`/journeys/recommendations`, `/journeys/{id}/suggestions`.

- Render the image as the card header / cover when non-null; keep the existing
  emoji `icon` treatment as fallback when null. `object-fit: cover`, fixed
  aspect (suggest 16:9 crop of the 1024×1024 source), `loading="lazy"`,
  `alt={journey.title}`.
- **The URL lands asynchronously**, ~5–30s after `/explore/confirm` returns
  (background task). Options, in order of preference:
  1. Do nothing special — the card shows the emoji now and the image on next
     fetch (list/recommendations responses will carry it). Cheapest, fine for v1.
  2. On the journey detail page, if `hero_image_url` is null and the journey is
     <2min old, refetch `GET /journeys/{id}` once after ~15s.
- No skeleton shimmer needed if going with option 1.
- Curated journeys get URLs after `scripts/generate_curated_heroes.py` is run
  and the printed URLs are pasted into `SAMPLE_JOURNEYS`.

## 2. Diagrams inside step content

Step `content` markdown can now contain **one** of:

- a fenced ` ```mermaid ` code block (flowchart TD/LR or sequenceDiagram) —
  render with mermaid.js (lazy-load the lib only when a mermaid block is
  present; wrap in an error boundary so a syntax error degrades to showing
  nothing, not a crash);
- an inline `<svg viewBox="0 0 640 360">…</svg>` — **server-sanitized**
  (allowlisted shapes/text only, no scripts/handlers/hrefs — see
  `sanitize_step_diagrams` in `ai_service.py`). The markdown renderer's
  sanitizer must allow `svg` + basic shape/text/gradient tags **for API-served
  step content only**; keep sanitization strict everywhere else.

Styling: `max-width: 100%`, center, `currentColor`-friendly is not guaranteed —
diagrams assume light background; give them a white/neutral card in dark mode.

Existing cached steps regenerate lazily (prompt v3) as users view them, so
diagrams appear on old journeys gradually — no forced migration.
