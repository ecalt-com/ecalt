-- Add quiz_anchors column to step_content for content-quiz contract (Phase 4)
ALTER TABLE step_content
ADD COLUMN IF NOT EXISTS quiz_anchors JSONB DEFAULT '[]'::jsonb;
