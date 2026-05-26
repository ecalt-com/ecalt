-- Stripe Test Environment: Seed plan_configs with test price IDs
-- Run this after creating products in the Stripe test dashboard.
-- Replace the price_REPLACE_... placeholders with your actual test Price IDs.
--
-- To find Price IDs: Stripe Dashboard → Products → click a product → copy "Price ID"
-- Test Price IDs look like: price_1AbcDefGhiJklMno

-- ─── Ensure base plans exist ────────────────────────────────────────────────

INSERT INTO plan_configs (plan_id, name, base_price_cents, token_budget_cents, lifetime_message_limit, is_active)
VALUES
  ('free_trial',  'Free Trial',  0,    20,    6,    true),
  ('individual',  'Individual',  999,  5000,  NULL, true)
ON CONFLICT (plan_id) DO NOTHING;

-- ─── Wire Stripe Price IDs ───────────────────────────────────────────────────
-- Replace these with the Price IDs from your Stripe test dashboard.

UPDATE plan_configs
SET stripe_price_id = 'price_REPLACE_WITH_INDIVIDUAL_PRICE_ID'
WHERE plan_id = 'individual';

-- If you have a team plan:
-- UPDATE plan_configs
-- SET stripe_price_id = 'price_REPLACE_WITH_TEAM_PRICE_ID'
-- WHERE plan_id = 'team';

-- ─── Verify ─────────────────────────────────────────────────────────────────

SELECT
    plan_id,
    name,
    base_price_cents,
    token_budget_cents,
    stripe_price_id,
    is_active
FROM plan_configs
ORDER BY base_price_cents;

-- Expected output:
-- plan_id    | name        | base_price_cents | token_budget_cents | stripe_price_id       | is_active
-- -----------+-------------+------------------+--------------------+-----------------------+-----------
-- free_trial | Free Trial  | 0                | 20                 | NULL                  | true
-- individual | Individual  | 999              | 5000               | price_1Abc...         | true
