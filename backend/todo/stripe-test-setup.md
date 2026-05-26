# Stripe Test Environment Setup Plan

## Overview

This plan walks through connecting the local ecalt backend to Stripe's test mode end-to-end:
keys → products → DB seed → webhook CLI → test checkout → verify subscription upsert.

The codebase already has the full integration wired (`subscriptions.py`, `subscription_service.py`).
Nothing needs to be written — only configured and verified.

---

## Step 1 — Get Stripe Test Keys

1. Go to https://dashboard.stripe.com and log in (or create a free account).
2. Make sure the toggle in the top-right says **Test mode** (not Live).
3. Go to **Developers → API keys**.
4. Copy:
   - **Publishable key** — starts with `pk_test_`
   - **Secret key** — starts with `sk_test_`

---

## Step 2 — Configure `.env`

Edit `backend/.env` (copy from `.env.example` if it doesn't exist):

```env
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_FILL_IN_AFTER_STEP_4
FRONTEND_URL=http://localhost:3000
```

`STRIPE_WEBHOOK_SECRET` is filled in after Step 4 (Stripe CLI).

---

## Step 3 — Create Test Products & Prices in Stripe Dashboard

The code maps Stripe price IDs to plan_ids via `plan_configs.stripe_price_id`
(see `_stripe_price_to_plan()` in `subscriptions.py:L158` and `create_checkout()` at `L80-L95`).
You need at least one product+price in Stripe that maps to a row in `plan_configs`.

### In Stripe Dashboard → Products → Add Product

Create one product per paid plan. For each:

| Plan          | Name in Stripe       | Billing       | Amount  |
|---------------|----------------------|---------------|---------|
| individual    | ecalt Individual     | Monthly       | $9.99   |
| team (opt.)   | ecalt Team           | Monthly       | $29.99  |

For each product, Stripe will generate a **Price ID** like `price_1AbcDef...`.
Copy these — you need them in Step 3b.

> In test mode you can use any amount. The values above are examples.

### 3b — Seed `plan_configs` with Stripe Price IDs

Run this SQL against your Supabase DB (update price IDs from above):

```sql
-- See todo/stripe-seed-plan-configs.sql for the full seed file
UPDATE plan_configs
SET stripe_price_id = 'price_REPLACE_WITH_INDIVIDUAL_PRICE_ID'
WHERE plan_id = 'individual';

-- Add more rows for additional paid plans as needed
```

See **`todo/stripe-seed-plan-configs.sql`** for the full idempotent seed.

Verify the `free_trial` plan row exists (no `stripe_price_id` needed — it's not purchasable):
```sql
SELECT plan_id, name, stripe_price_id, is_active FROM plan_configs ORDER BY base_price_cents;
```

---

## Step 4 — Install Stripe CLI and Forward Webhooks

The webhook handler is at `POST /api/v1/subscriptions/webhook` (`subscriptions.py:L110`).
It verifies `stripe-signature` using `STRIPE_WEBHOOK_SECRET`, so you must forward via the CLI.

### Install Stripe CLI

```bash
# macOS
brew install stripe/stripe-cli/stripe

# or via curl
curl -s https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
```

### Log in

```bash
stripe login
# Opens browser — authorize with your Stripe account
```

### Forward to local server

```bash
stripe listen --forward-to localhost:8000/api/v1/subscriptions/webhook
```

The CLI prints a **webhook signing secret** starting with `whsec_`. Copy it.

Update `backend/.env`:
```env
STRIPE_WEBHOOK_SECRET=whsec_PASTE_FROM_CLI_OUTPUT
```

Restart the backend after updating `.env`.

> Keep this terminal open while testing — it relays all Stripe events to your local server.

---

## Step 5 — Start the Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Verify the subscriptions endpoint is reachable:
```bash
curl http://localhost:8000/api/v1/subscriptions/plans
# Should return {"plans": [...]} — the plan_configs rows
```

---

## Step 6 — Test the Checkout Flow

### 6a — Trigger a checkout session

Call the checkout endpoint with a valid Firebase auth token:

```bash
curl -X POST http://localhost:8000/api/v1/subscriptions/checkout \
  -H "Authorization: Bearer YOUR_FIREBASE_ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_id": "individual"}'
# Returns {"checkout_url": "https://checkout.stripe.com/..."}
```

Open the `checkout_url` in a browser.

### 6b — Complete payment with a test card

On the Stripe checkout page, use a test card from `todo/stripe-test-cards.md`:

| Scenario            | Card Number         | Exp    | CVC  |
|---------------------|---------------------|--------|------|
| Success             | 4242 4242 4242 4242 | 12/34  | 123  |
| Auth required (3DS) | 4000 0027 6000 3184 | 12/34  | 123  |
| Card declined       | 4000 0000 0000 9995 | 12/34  | 123  |

Use any name, any valid future expiry. ZIP: 12345.

### 6c — Verify webhook delivery

In the `stripe listen` terminal you should see:

```
--> checkout.session.completed [evt_...]   200 OK
```

This triggers `upsert_subscription_from_stripe()` (`subscription_service.py:L263`),
which inserts/updates the `subscriptions` table.

### 6d — Confirm subscription was created in DB

```sql
SELECT uid, plan_id, stripe_subscription_id, status, current_period_end
FROM subscriptions
ORDER BY created_at DESC
LIMIT 5;
```

### 6e — Verify via the `/me` endpoint

```bash
curl http://localhost:8000/api/v1/subscriptions/me \
  -H "Authorization: Bearer YOUR_FIREBASE_ID_TOKEN"
# plan.plan_id should now be "individual", not "free_trial"
```

---

## Step 7 — Test Subscription Lifecycle Events

Use Stripe CLI to fire events without going through the UI:

```bash
# Simulate subscription cancellation
stripe trigger customer.subscription.deleted

# Simulate subscription update (e.g. plan change)
stripe trigger customer.subscription.updated
```

After each event, re-query `subscriptions.status` in the DB to confirm
the `UPDATE subscriptions SET status = ...` branch at `subscriptions.py:L148` fired.

---

## Step 8 — Test Edge Cases

| Scenario                         | How to test                                                                 |
|----------------------------------|-----------------------------------------------------------------------------|
| Missing `STRIPE_SECRET_KEY`      | Blank it in `.env`, restart — checkout returns 503                          |
| Invalid webhook signature        | Send a raw POST to `/webhook` without CLI — returns 400                     |
| Plan not found in DB             | POST checkout with `plan_id: "nonexistent"` — returns 404                   |
| Plan has no `stripe_price_id`    | Clear `stripe_price_id` in DB for a plan — returns 503                      |
| Card declined                    | Use card `4000 0000 0000 9995` — checkout shows decline, no webhook fires   |
| 3DS auth required                | Use card `4000 0027 6000 3184` — complete auth challenge, webhook fires      |

---

## Step 9 — Verify Frontend Redirect

After a successful test checkout, Stripe redirects to:
```
http://localhost:3000/learn?upgraded=true
```

Confirm the frontend handles `?upgraded=true` (e.g. shows an upgrade banner).
The URL is built from `settings.FRONTEND_URL` in `create_checkout()` at `subscriptions.py:L103`.

---

## Environment Summary

Full `.env` block for Stripe test mode:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...   # from: stripe listen output
FRONTEND_URL=http://localhost:3000
```

---

## Files in This Todo

| File                           | Purpose                                      |
|--------------------------------|----------------------------------------------|
| `stripe-test-setup.md`         | This plan                                    |
| `stripe-test-cards.md`         | Full test card reference for all scenarios   |
| `stripe-seed-plan-configs.sql` | Idempotent SQL to wire price IDs to plans    |
