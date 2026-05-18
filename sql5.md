# Phase 5 SQL — Run in Supabase SQL Editor

```sql
-- Fix unit bug: token_budget_cents was stored as dollars, should be cents
-- 40% of plan price, expressed in cents
UPDATE plan_configs SET token_budget_cents = CASE
  WHEN plan_id = 'free_trial'  THEN 20.0       -- $0.20/month for non-chat AI
  WHEN plan_id = 'individual'  THEN 760.0      -- $7.60 = 40% of $19
  WHEN plan_id = 'student'     THEN 360.0      -- $3.60 = 40% of $9
  WHEN plan_id = 'family'      THEN 1560.0     -- $15.60 = 40% of $39
  WHEN plan_id = 'university'  THEN 11960.0    -- $119.60 = 40% of $299
  WHEN plan_id = 'enterprise'  THEN 19900.0    -- $199.00 = 40% of $499
  ELSE token_budget_cents
END;

-- Coupons (admin-created promo codes)
CREATE TABLE IF NOT EXISTS coupons (
  code text primary key,
  description text,
  credit_cents float default 0,              -- extra AI token budget in cents
  bonus_messages int default 0,              -- extra chat messages for free trial users
  plan_override text references plan_configs(plan_id), -- null = no plan upgrade
  duration_days int,                         -- null = permanent; N = credit active for N days after redemption
  max_redemptions int,                       -- null = unlimited
  redemption_count int default 0,
  expires_at timestamptz,                    -- null = no expiry date
  is_active boolean default true,
  created_at timestamptz default now()
);

-- Who redeemed which coupon
CREATE TABLE IF NOT EXISTS coupon_redemptions (
  id uuid primary key default gen_random_uuid(),
  uid text references users(uid) on delete cascade,
  coupon_code text references coupons(code),
  credit_applied_cents float default 0,
  bonus_messages_applied int default 0,
  credit_expires_at timestamptz,             -- null = permanent
  redeemed_at timestamptz default now(),
  unique(uid, coupon_code)                   -- one redemption per user per coupon
);

CREATE INDEX IF NOT EXISTS coupon_redemptions_uid_idx ON coupon_redemptions(uid);
```
