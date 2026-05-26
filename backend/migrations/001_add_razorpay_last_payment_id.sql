-- M2: Add column for Razorpay payment replay prevention
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS razorpay_last_payment_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_razorpay_last_payment_id_idx
    ON subscriptions (razorpay_last_payment_id)
    WHERE razorpay_last_payment_id IS NOT NULL;
