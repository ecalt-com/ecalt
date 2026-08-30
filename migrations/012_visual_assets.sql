-- ECALT Visual Intelligence Layer — Phase 5/6 asset storage.
-- Shared by retrieved (licensed/open) assets and generated (AI image/video)
-- assets alike (spec section 6.2) — both attach to a VLO the same way.

CREATE TABLE visual_assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vlo_id uuid NOT NULL REFERENCES visual_learning_objects(id) ON DELETE CASCADE,
    asset_type text NOT NULL,
    storage_key text,
    external_url text,
    source_type text,
    source_name text,
    license_type text,
    license_url text,
    attribution text,
    commercial_use_allowed boolean,
    modification_allowed boolean,
    width integer,
    height integer,
    duration_ms integer,
    file_size_bytes bigint,
    checksum text,
    status text NOT NULL DEFAULT 'pending',
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE visual_assets
    ADD CONSTRAINT visual_assets_asset_type_check
    CHECK (asset_type IN ('svg', 'png', 'jpg', 'webp', 'webm', 'mp4', 'gif', 'interactive', 'external_embed'));

ALTER TABLE visual_assets
    ADD CONSTRAINT visual_assets_status_check
    CHECK (status IN ('pending', 'validating', 'active', 'blocked', 'failed'));

CREATE INDEX idx_visual_assets_vlo ON visual_assets (vlo_id);

ALTER TABLE visual_assets ENABLE ROW LEVEL SECURITY;
