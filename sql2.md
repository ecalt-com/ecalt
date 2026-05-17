# Phase 2 — Supabase Migrations

Paste this entire block into **Supabase → SQL Editor → New query → Run**.

```sql
-- Add is_admin flag to existing users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin boolean default false;

-- Plan configuration (admin-adjustable)
CREATE TABLE IF NOT EXISTS plan_configs (
  plan_id                 text primary key,
  name                    text not null,
  base_price_cents        int not null,
  token_budget_cents      int not null,
  lifetime_message_limit  int,
  max_seats               int default 1,
  is_active               boolean default true,
  stripe_price_id         text,
  updated_at              timestamptz default now()
);

-- Seed default plans
INSERT INTO plan_configs (plan_id, name, base_price_cents, token_budget_cents, lifetime_message_limit, max_seats)
VALUES
  ('free_trial',  'Free Trial',   0,     2,     6,    1),
  ('individual',  'Individual',   1900,  760,   null, 1),
  ('student',     'Student',      900,   360,   null, 1),
  ('family',      'Family',       3900,  1560,  null, 5),
  ('university',  'University',   29900, 11960, null, 100),
  ('enterprise',  'Enterprise',   49900, 19900, null, 500)
ON CONFLICT (plan_id) DO NOTHING;

-- User subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
  id                     uuid primary key default gen_random_uuid(),
  uid                    text references users(uid) on delete cascade unique,
  plan_id                text references plan_configs(plan_id) default 'free_trial',
  stripe_subscription_id text unique,
  stripe_customer_id     text,
  status                 text not null default 'active',
  current_period_start   timestamptz,
  current_period_end     timestamptz,
  created_at             timestamptz default now()
);

-- Token usage per billing period
CREATE TABLE IF NOT EXISTS token_usage (
  uid                   text references users(uid) on delete cascade,
  period_start          date not null,
  input_tokens          bigint default 0,
  output_tokens         bigint default 0,
  estimated_cost_cents  float default 0,
  message_count         int default 0,
  updated_at            timestamptz default now(),
  primary key (uid, period_start)
);

CREATE INDEX IF NOT EXISTS subscriptions_uid_idx ON subscriptions(uid);
CREATE INDEX IF NOT EXISTS token_usage_uid_idx ON token_usage(uid, period_start);
```
