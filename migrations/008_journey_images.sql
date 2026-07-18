-- Journey images (plans/journey-images): hero image per journey + optional
-- per-step illustration (Phase 3, on-demand).
ALTER TABLE journeys     ADD COLUMN IF NOT EXISTS hero_image_url TEXT;
ALTER TABLE step_content ADD COLUMN IF NOT EXISTS image_url      TEXT;

-- Public-read storage bucket for generated images. Uploads go through the
-- backend with the service-role key (bypasses RLS); public=true serves reads
-- at /storage/v1/object/public/journey-images/... without auth.
INSERT INTO storage.buckets (id, name, public)
VALUES ('journey-images', 'journey-images', true)
ON CONFLICT (id) DO NOTHING;
