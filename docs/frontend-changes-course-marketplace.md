# Frontend: Course Marketplace

> **Status: BACKEND ONLY** — no frontend files touched. This doc is the endpoint reference for building the UI.

Backend now supports a marketplace of popular, admin-approved user-generated journeys. A journey becomes eligible **automatically** (no creator action) once a scheduled job (`_marketplace_popularity_scan`, every 6h) sees enough unique learners or likes; an admin then approves/rejects it from a review queue before it's publicly listed. Three new surfaces need UI.

## 1. Browse the marketplace

```
GET /api/v1/journeys/marketplace?age_group=&difficulty=&tag=&limit=20&offset=0
Authorization: optional (public browsing, like the curated journeys today)

Response 200:
{
  "journeys": [ <Journey>, ... ],   // same shape as GET /journeys, plus the fields below
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

`Journey` objects everywhere (including this list, `GET /journeys`, `GET /journeys/{id}`) now also carry:
```
"marketplace_status": "private" | "pending_review" | "published" | "rejected",
"popularity_score": 17.0,
"like_count": 4,
"forked_from_id": "source-journey-id" | null
```
Only `published` journeys ever appear in the marketplace listing; the other fields are informational for anywhere a `Journey` is already rendered.

Suggested UX: a new `/marketplace` route — a grid/list of cards sorted by popularity (server already orders by `popularity_score DESC`), with filter chips for `age_group`/`difficulty`/`tag`. When signed in, your own journeys are already excluded server-side. Empty state is likely for a while — see the "Confirmed decisions" note in the backend plan: promotion thresholds are new and starter values, so expect zero or few `published` journeys until an admin approves the first ones.

## 2. Like a journey

```
POST /api/v1/journeys/{journey_id}/like
Authorization: required (acting uid)

Response 200:
{ "liked": true | false, "like_count": 5 }
```
Toggle — call it again to unlike. Works on any journey (not just marketplace ones), feeding the popularity score for its creator. Suggested UX: a heart/like button on the journey detail page showing `like_count`, filled/unfilled based on the last response (no separate "did I like this" endpoint — track the toggle state client-side after the first call, or seed it from `like_count` context if you fetch a per-user liked list later).

## 3. Add a marketplace journey to your own list ("fork")

```
POST /api/v1/journeys/{journey_id}/fork
Authorization: required (acting uid)

Response 200 (same shape as POST /explore/confirm):
{ "journey": <Journey with a new id, forked_from_id = source id> }

404 if the journey isn't currently marketplace_status = "published".
```
Creates an independent copy under the caller's own account — separate progress, and it starts private again (must earn its own popularity to reach the marketplace itself). Suggested UX: an "Add to my journeys" button on a marketplace card/detail page; on success, navigate to `/journey/{new_id}` same as after `/explore/confirm` today.

## 4. Admin: marketplace review queue (new admin panel section)

```
GET  /api/v1/admin/marketplace-queue
     → { "queue": [{ id, uid, title, description, icon, age_group, difficulty,
                      popularity_score, like_count, created_at }, ...] }

POST /api/v1/admin/marketplace-queue/{journey_id}/approve   → publishes it
POST /api/v1/admin/marketplace-queue/{journey_id}/reject    → rejected, won't be re-flagged
POST /api/v1/admin/marketplace-queue/{journey_id}/reset     → back to private (unpublish, or give a rejected one another chance)
```
All admin-gated (`is_admin`), same pattern as the rest of the admin panel. Suggested UX: a "Marketplace Queue" tab listing pending journeys sorted by popularity (already sorted server-side) with Approve/Reject buttons; a way to unpublish from the main journey list (Reset) for after-the-fact moderation.
