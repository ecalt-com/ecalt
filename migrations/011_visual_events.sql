-- ECALT Visual Intelligence Layer — Phase 4 telemetry.
-- Append-only event log (spec section 22) feeding effectiveness measurement
-- (spec section 23). uid is nullable — sparks and other unauthenticated
-- surfaces may eventually emit visual events without a logged-in user.

CREATE TABLE visual_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    uid text REFERENCES users(uid),
    journey_id text,
    step_id text,
    vlo_id uuid REFERENCES visual_learning_objects(id),
    session_id text,
    event_type text NOT NULL,
    event_data jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE visual_events
    ADD CONSTRAINT visual_events_event_type_check
    CHECK (event_type IN (
        'visual_impression', 'visual_started', 'visual_completed',
        'visual_replayed', 'visual_skipped', 'visual_interaction', 'visual_error'
    ));

CREATE INDEX idx_visual_events_vlo ON visual_events (vlo_id);
CREATE INDEX idx_visual_events_journey_step ON visual_events (journey_id, step_id);
CREATE INDEX idx_visual_events_created_at ON visual_events (created_at);

ALTER TABLE visual_events ENABLE ROW LEVEL SECURITY;
