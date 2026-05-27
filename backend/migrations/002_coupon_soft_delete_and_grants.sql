-- M3: Coupon soft-delete, updated_at tracking, and grant tag support

ALTER TABLE coupons ADD COLUMN IF NOT EXISTS is_deleted  boolean     NOT NULL DEFAULT false;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS deleted_at  timestamptz;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS updated_at  timestamptz DEFAULT now();
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS tag         text;

CREATE INDEX IF NOT EXISTS coupons_is_deleted_idx  ON coupons (is_deleted);
CREATE INDEX IF NOT EXISTS coupons_tag_idx         ON coupons (tag);
