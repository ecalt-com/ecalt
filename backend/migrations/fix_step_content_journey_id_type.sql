-- Fix step_content.journey_id and step_id column types from uuid to text.
-- The journey IDs are slug strings like "journey-climate", not UUIDs.

ALTER TABLE step_content
  ALTER COLUMN journey_id TYPE text USING journey_id::text,
  ALTER COLUMN step_id    TYPE text USING step_id::text;
