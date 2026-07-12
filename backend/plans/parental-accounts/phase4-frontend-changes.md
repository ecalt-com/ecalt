# Phase 4 — Frontend changes required

Backend Phase 4 (parental controls) is implemented: settings PATCH with real
enforcement, self-serve consent revocation with a 14-day grace window, parent
child-data export, and Family-plan seat sharing. No new migration was needed.

---

## 1. Child settings panel (`/family/child/:uid`)

`PATCH /api/v1/family/children/{uid}/settings` — send only the fields being changed:

```jsonc
// request (all optional)
{
  "paused": true,
  "chat_enabled": false,
  "content_age_band": "kids" | "teens" | "adults" | "all",
  "transcript_visibility": "summaries" | "full",
  "weekly_digest_enabled": true
}
// response
{ "child_uid": "…", "settings": { "paused": …, "chat_enabled": …, "content_age_band": …,
                                   "transcript_visibility": …, "weekly_digest_enabled": … } }
```

Suggested toggles, with honest helper text about what each does:
- **Pause account** — child can't use ECALT at all (403 `account_paused` on all learning endpoints).
- **AI chat** — blocks the chat panel and journey tutor (403 `chat_disabled`).
- **Content level** — overrides the age band used for journey generation, whatever the child's client sends.
- **Conversation access** — `full` lets the parent open transcripts (Phase 3 endpoint); the child's transparency banner updates automatically.
- **Weekly digest** — the Sunday summary email.

## 2. Child-side error states (required)

Learning endpoints (`/chat/stream`, `/explore/*`, `/quiz/*`) now return new 403s
the child's UI must render kindly:

| `detail.error` | Where | Suggested UI |
|---|---|---|
| `account_paused` | everywhere | Full-screen: "Your account is paused. Ask your parent to unpause it." |
| `chat_disabled` | chat/tutor | Inline in the chat panel: "AI chat is turned off for your account." |
| `consent_pending` | everywhere (existed) | unchanged |

Note: `/explore/*` and `/quiz/*` previously accepted any authenticated user; they
now also 403 for consent-pending accounts — no UI change needed beyond the above.

## 3. Consent revocation (child detail page, "Danger zone")

- `POST /api/v1/family/children/{uid}/revoke-consent` →
  `{ "status": "revoked", "message": "…paused now, deleted in 14 days…" }`
  (409 `already_scheduled` if pending). Confirm dialog should offer "Download
  their data first" (see §4). After revoking, show a countdown banner on the
  child card with an **Undo** button.
- `POST /api/v1/family/children/{uid}/revoke-consent/cancel` →
  `{ "status": "restored", … }` (404 `nothing_scheduled`).
- The parent also gets an email receipt with the grace deadline.
- There is no "is deletion scheduled?" field on the children list yet — infer from
  the revoke response in-session, or treat `paused: true` as the hint and let the
  cancel endpoint's 404 disambiguate. (Field can be added on request.)

## 4. Child data export

`GET /api/v1/family/children/{uid}/export` — same shape as the user's own
`/users/me/export`, downloadable JSON (`Content-Disposition: attachment`). Add a
"Download data" button on the child detail page and in the revocation dialog.

## 5. Family plan seats (Pricing / SubscriptionContext)

Children without their own subscription now automatically inherit a linked
parent's **Family** plan (first 4 children by link age; parent + 4 = 5 seats), and
the family shares one token budget — `GET /subscriptions/me` on any member shows
the combined family spend. Pricing page copy for the Family plan can now truthfully
say "up to 5 members, shared budget"; no API changes required.
