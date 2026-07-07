# Frontend: Step Feedback + Regenerate Content

> **Status: IMPLEMENTED (2026-07-07)** — `src/components/StepFeedbackBar.tsx`, rendered from `StepNode.tsx` below the lesson content for signed-in users; API wrappers `submitStepFeedback` / `regenerateStepContent` in `src/lib/api.ts`. This doc remains as the endpoint reference.

Backend support shipped with the course-content-quality upgrade (see `backend/plans/course-content-quality/`). Two new endpoints need UI in the Journey step view.

## 1. Step feedback (thumbs + tag)

```
POST /api/v1/journeys/{journey_id}/steps/{step_id}/feedback
Authorization: required (acting uid)

Body:
{
  "rating": "up" | "down",                     // required
  "tag": "too_generic" | "too_basic" | "too_advanced" | "inaccurate" | "loved_it",  // optional
  "comment": "free text, max 500 chars"        // optional
}

Response 200:
{ "ok": true, "regenerating": true | false }
```

Behavior:
- One feedback row per (user, journey, step) — resubmitting **overwrites** the previous rating (upsert), so the UI can let users change their mind freely.
- If `tag` is `too_generic`, `too_basic`, or `too_advanced`, the backend **automatically regenerates the step content in the background** with a tag-specific instruction. `regenerating: true` signals this.

Suggested UX:
- 👍 / 👎 at the bottom of step content. On 👎, show tag chips: "Too generic" / "Too basic" / "Too advanced" / "Something's wrong" (`inaccurate`) + optional comment field.
- When `regenerating: true` comes back, show a toast: "Got it — we're rewriting this step for you. Check back in a minute." The next fetch of the step content returns the new version once regeneration completes (a few seconds to ~1 min). No push signal — refetch on next visit or offer a refresh affordance.

## 2. Explicit regenerate ("Give me a fresh take")

```
POST /api/v1/journeys/{journey_id}/steps/{step_id}/content/regenerate
Authorization: required (acting uid)
Rate limit: 10/hour per IP. Budget-checked (402 with upgrade_url when exhausted).

Response 200: same shape as GET .../content
{ "journey_id": "...", "step_id": "...", "content": "...", "cached": false }
```

Behavior:
- **Synchronous** — the response body already contains the new content (typically 5–20 s; show a loading state).
- Overwrites the cached content for everyone viewing that journey step.
- Errors: `402` budget exhausted, `429` rate-limited, `502/503` AI upstream issues — show a retry-later message.

Suggested UX: a subtle "↻ Fresh take" action in the step content header/menu, with a confirm since it replaces the current text.

## 3. Existing content quietly improves (no UI required)

`GET .../steps/{step_id}/content` now serves cached content immediately but, when that content was generated under an older prompt version, refreshes it in the background. Users may notice step content improving between visits — this is expected. If desired later, the response could expose a `refreshed` flag; not implemented today.
