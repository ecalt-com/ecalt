# ECALT — Operations & Admin Guide

> This document covers: pricing page fixes, admin system setup, and how to manage users and plans after launch.

---

## 1. Pricing Page

### What changed
- Free tier card is now visible (was previously filtered out)
- Removed marketing tagline; replaced with neutral description
- Free tier button shows "Free forever" and is non-clickable

### Navigation
- "Pricing" appears in the top nav on all pages (Home, Explore, Journeys, Passport)
- "Pricing" also appears in the Learn page header
- Direct URL: `/pricing`

---

## 2. Admin System

### How admin access works
- Each user row has an `is_admin boolean` column in the `users` table
- The `/admin` page and all `/api/v1/admin/*` endpoints require `is_admin = true`
- Non-admin users are redirected to `/` when they hit a 403
- The **Admin nav link only appears for admin users** — it is invisible to everyone else

### Making the first admin (bootstrap)

Three options, in order of preference:

#### Option A — Bootstrap endpoint (easiest, one-time)
Works only when **zero admins exist** in the database. After the first admin is created, this endpoint returns 403.

```bash
# The user must have signed in at least once (so their row exists in the users table)

curl -X POST https://your-backend.railway.app/api/v1/admin/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'

# Or by Firebase UID:
curl -X POST https://your-backend.railway.app/api/v1/admin/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"uid": "abc123firebaseuid"}'
```

Response:
```json
{ "promoted": { "uid": "...", "email": "you@example.com", "display_name": "You" } }
```

#### Option B — CLI script (local or server)
Run from the `backend/` directory with `DATABASE_URL` set in `.env`:

```bash
cd backend
source .venv/bin/activate

# Grant admin
python scripts/make_admin.py --email you@example.com

# Grant by UID
python scripts/make_admin.py --uid abc123firebaseuid

# Revoke admin
python scripts/make_admin.py --email you@example.com --revoke
```

Requires: `DATABASE_URL` in `backend/.env`  
Format: `postgresql://user:pass@host:port/dbname`

#### Option C — Admin panel (after first admin exists)
1. Sign in as an existing admin
2. Navigate to `/admin` → **Users** tab
3. Find the user and click **Grant** (shield icon)
4. To revoke: click **Revoke** on any admin user

---

## 3. Admin Panel — What's Inside

The `/admin` page has three tabs:

### Overview tab
- Total users, DAU, messages today, monthly API cost
- Quick grid of all active plans and their prices

### Pricing Plans tab
Top half: **live preview** of all 6 pricing cards exactly as users see them on `/pricing`.

Bottom half: **editable plan config** — change any plan's:
| Field | What it controls |
|---|---|
| Price (cents) | What's shown on the pricing page and charged via Stripe |
| Token budget (cents) | How much Claude API spend a user gets per billing period |
| Stripe price ID | The `price_xxx` from Stripe dashboard — required for checkout |
| Max seats | Max users under this plan (e.g. 5 for Family, 100 for University) |

Click **Save** after editing any plan row. Changes take effect immediately for new checkouts.

### Users tab
- Lists up to 100 most-recent users with their current plan
- Admin badge shown next to admin users
- **Grant / Revoke** button for each user — toggles `is_admin`
- You cannot accidentally self-revoke from this view (the toggle works on any uid including yourself, so be careful)

---

## 4. Plan Configuration Reference

| Plan ID | Name | Price | Token budget | Message limit | Seats |
|---|---|---|---|---|---|
| `free_trial` | Free Trial | $0 | 2¢ | 6 lifetime | 1 |
| `individual` | Individual | $19/mo | 760¢ | unlimited | 1 |
| `student` | Student | $9/mo | 360¢ | unlimited | 1 |
| `family` | Family | $39/mo | 1560¢ | unlimited | 5 |
| `university` | University | $299/mo | 11960¢ | unlimited | 100 |
| `enterprise` | Enterprise | $499/mo | 19900¢ | unlimited | 500 |

**Token budget** = 40% of plan price, converted to estimated Claude API cost (¢).  
Haiku: $0.08/M input, $0.40/M output · Sonnet: $0.30/M input, $1.50/M output

---

## 5. Stripe Setup (to enable paid plans)

1. Create a product in the [Stripe dashboard](https://dashboard.stripe.com) for each paid plan
2. Copy each plan's **price ID** (format: `price_xxx`)
3. In the Admin panel → Pricing Plans tab, paste the price ID for each plan and click Save
4. Add to Railway environment variables:
   - `STRIPE_SECRET_KEY` — from Stripe dashboard → Developers → API keys
   - `STRIPE_WEBHOOK_SECRET` — from Stripe dashboard → Webhooks (point to `your-backend/api/v1/subscriptions/webhook`)
5. Add to Vercel environment variables:
   - `VITE_STRIPE_PUBLISHABLE_KEY` — publishable key from Stripe (not used directly yet but needed for future client-side Stripe Elements)

---

## 6. API Endpoints Reference

### Admin endpoints (all require `is_admin = true`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/admin/plans` | All plan configs |
| `PATCH` | `/api/v1/admin/plans/{plan_id}` | Update a plan config |
| `GET` | `/api/v1/admin/stats` | DAU, messages, cost |
| `GET` | `/api/v1/admin/users` | Recent 100 users |
| `PATCH` | `/api/v1/admin/users/{uid}/toggle-admin` | Toggle admin flag |

### Bootstrap endpoint (no auth, one-time)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/admin/bootstrap` | Promote first admin (fails if any admin exists) |

Body: `{ "email": "..." }` or `{ "uid": "..." }`

---

## 7. Files Changed in This Session

| File | Change |
|---|---|
| `frontend/src/components/Navigation.tsx` | Added "Pricing" to nav; "Admin" link added, visible only to admins |
| `frontend/src/pages/Learn.tsx` | Added Pricing + Admin (admin-only) links to header |
| `frontend/src/pages/Pricing.tsx` | Show free_trial card; removed marketing tagline; free tier button non-clickable |
| `frontend/src/pages/Admin.tsx` | Full rewrite: 3-tab layout (Overview / Pricing Plans / Users), live pricing preview, admin toggle per user |
| `frontend/src/lib/SubscriptionContext.tsx` | Added `isAdmin` field, read from `/subscriptions/me` |
| `backend/app/api/v1/endpoints/subscriptions.py` | `/me` now returns `is_admin` flag |
| `backend/app/api/v1/endpoints/admin.py` | Added `POST /bootstrap`, `GET /users` (includes `is_admin`), `PATCH /users/{uid}/toggle-admin` |
| `backend/scripts/make_admin.py` | CLI script: grant/revoke admin by email or UID |
