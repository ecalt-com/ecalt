-- Track Stripe Product ID so we can create new Prices without duplicating Products
ALTER TABLE plan_configs
  ADD COLUMN IF NOT EXISTS stripe_product_id TEXT;
