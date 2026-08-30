-- ECALT Visual Intelligence Layer v1 — Phase 1 domain foundation.
-- Adds the two tables the planner/router need: a canonical reusable visual
-- teaching object (VLO) and an audit trail of every visual planning decision
-- made for a journey step. Asset storage, job queue, and telemetry tables
-- land in their own migrations alongside the phases that use them.

CREATE TABLE visual_learning_objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_key text NOT NULL,
    learning_objective_hash text NOT NULL,
    grade_band text NOT NULL,
    modality text NOT NULL,
    pedagogical_role text NOT NULL,
    renderer_type text,
    recipe jsonb NOT NULL DEFAULT '{}',
    content_hash text NOT NULL,
    version integer NOT NULL DEFAULT 1,
    status text NOT NULL DEFAULT 'draft',
    effectiveness_score numeric,
    reuse_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE visual_learning_objects
    ADD CONSTRAINT vlo_status_check
    CHECK (status IN ('draft', 'queued', 'rendering', 'validating', 'active', 'deprecated', 'failed', 'blocked'));

CREATE UNIQUE INDEX idx_vlo_identity ON visual_learning_objects (
    concept_key, learning_objective_hash, grade_band, modality, content_hash, version
);
CREATE INDEX idx_vlo_lookup ON visual_learning_objects (concept_key, learning_objective_hash, grade_band, modality)
    WHERE status = 'active';

ALTER TABLE visual_learning_objects ENABLE ROW LEVEL SECURITY;

CREATE TABLE visual_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    journey_id text NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    step_id text NOT NULL,
    concept_key text NOT NULL,
    plan jsonb NOT NULL,
    planner_model text,
    planner_prompt_version integer NOT NULL,
    estimated_cost_usd numeric,
    selected_strategy text,
    execution_status text NOT NULL DEFAULT 'planned',
    vlo_id uuid REFERENCES visual_learning_objects(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE visual_plans
    ADD CONSTRAINT visual_plans_execution_status_check
    CHECK (execution_status IN ('planned', 'queued', 'executing', 'ready', 'failed', 'skipped'));

-- One active visual slot per journey step for v1 (step-level granularity —
-- ECALT has no sub-step content-block id today); re-planning upserts in place.
CREATE UNIQUE INDEX idx_visual_plans_journey_step ON visual_plans (journey_id, step_id);

ALTER TABLE visual_plans ENABLE ROW LEVEL SECURITY;
