-- Add gateway tracking to subscriptions
ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS payment_gateway TEXT NOT NULL DEFAULT 'stripe'
    CHECK (payment_gateway IN ('stripe', 'razorpay')),
  ADD COLUMN IF NOT EXISTS razorpay_subscription_id TEXT,
  ADD COLUMN IF NOT EXISTS razorpay_customer_id TEXT;

-- Add INR pricing + Razorpay plan ID to plan_configs
ALTER TABLE plan_configs
  ADD COLUMN IF NOT EXISTS base_price_inr_paise  INTEGER,   -- price in paise (1 INR = 100 paise)
  ADD COLUMN IF NOT EXISTS razorpay_plan_id      TEXT;      -- Razorpay Plan ID (plan_XXXX)

-- Seed INR prices (adjust amounts as needed)
UPDATE plan_configs SET base_price_inr_paise = 0      WHERE plan_id = 'free_trial';
UPDATE plan_configs SET base_price_inr_paise = 79900  WHERE plan_id = 'individual';  -- ₹799/month
