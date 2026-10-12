-- Schools: tenants, staff, students, classes, school-built courses, source
-- documents, jobs, usage and audit. Additive and idempotent — safe to apply
-- before the backend deploys. See backend/plans/school-courses/README.md §3.2.
--
-- Tenant isolation is enforced in the schema as well as in code: link tables
-- carry school_id and reference their parents through (id, school_id) pairs,
-- so a row can never join a class, student or course from another school.

-- ── 1. Tenants and staff ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.schools (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                     text NOT NULL,
  slug                     text NOT NULL UNIQUE,
  country                  char(2) NOT NULL DEFAULT 'IN',
  status                   text NOT NULL DEFAULT 'onboarding'
                           CHECK (status IN ('onboarding', 'active', 'suspended', 'terminated')),
  seat_limit               integer NOT NULL DEFAULT 0 CHECK (seat_limit >= 0),
  monthly_ai_budget_cents  numeric NOT NULL DEFAULT 0 CHECK (monthly_ai_budget_cents >= 0),
  settings                 jsonb NOT NULL DEFAULT '{}'::jsonb,
  dpa_version              text,
  dpa_accepted_at          timestamptz,
  dpa_accepted_by          text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_by               text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now(),
  terminated_at            timestamptz
);

CREATE TABLE IF NOT EXISTS public.school_members (
  school_id   uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  uid         text NOT NULL REFERENCES public.users(uid) ON DELETE CASCADE,
  role        text NOT NULL CHECK (role IN ('owner', 'admin', 'teacher')),
  status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'removed')),
  invited_by  text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  removed_at  timestamptz,
  PRIMARY KEY (school_id, uid)
);
CREATE INDEX IF NOT EXISTS school_members_uid_idx ON public.school_members (uid) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS public.school_invites (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id     uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  email         text NOT NULL,                      -- lower-cased
  role          text NOT NULL CHECK (role IN ('owner', 'admin', 'teacher')),
  token_hash    text NOT NULL UNIQUE,               -- sha256 hex of the emailed token
  invited_by    text REFERENCES public.users(uid) ON DELETE SET NULL,
  expires_at    timestamptz NOT NULL,
  accepted_at   timestamptz,
  accepted_uid  text REFERENCES public.users(uid) ON DELETE SET NULL,
  revoked_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS school_invites_open_idx
  ON public.school_invites (school_id) WHERE accepted_at IS NULL AND revoked_at IS NULL;

-- ── 2. Students (a users row with profile_type='school_student', uid 'stu_<hex>') ──

CREATE TABLE IF NOT EXISTS public.school_students (
  uid               text PRIMARY KEY REFERENCES public.users(uid) ON DELETE CASCADE,
  school_id         uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  display_name      text NOT NULL,
  external_ref      text,                           -- school's own roll / admission number
  grade             smallint CHECK (grade BETWEEN 0 AND 12),
  avatar            text,
  status            text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  secret_kind       text NOT NULL DEFAULT 'picture' CHECK (secret_kind IN ('picture', 'pin')),
  secret_hash       text,                           -- scrypt$<salt>$<hash>
  failed_attempts   smallint NOT NULL DEFAULT 0,
  locked_until      timestamptz,
  badge_token_hash  text UNIQUE,
  created_by        text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  archived_at       timestamptz,
  UNIQUE (uid, school_id),
  UNIQUE (school_id, external_ref)
);
CREATE INDEX IF NOT EXISTS school_students_school_idx ON public.school_students (school_id, status);

-- ── 3. Classes ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.classes (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id      uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  name           text NOT NULL,
  grade          smallint CHECK (grade BETWEEN 0 AND 12),
  subject        text,
  academic_year  text,
  join_code      text NOT NULL UNIQUE,
  settings       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by     text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  archived_at    timestamptz,
  UNIQUE (id, school_id)
);
CREATE INDEX IF NOT EXISTS classes_school_idx ON public.classes (school_id) WHERE archived_at IS NULL;

CREATE TABLE IF NOT EXISTS public.class_teachers (
  class_id   uuid NOT NULL,
  school_id  uuid NOT NULL,
  uid        text NOT NULL,
  role       text NOT NULL DEFAULT 'lead' CHECK (role IN ('lead', 'co')),
  added_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (class_id, uid),
  FOREIGN KEY (class_id, school_id) REFERENCES public.classes(id, school_id) ON DELETE CASCADE,
  FOREIGN KEY (school_id, uid) REFERENCES public.school_members(school_id, uid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS class_teachers_uid_idx ON public.class_teachers (uid);

CREATE TABLE IF NOT EXISTS public.class_enrollments (
  class_id     uuid NOT NULL,
  school_id    uuid NOT NULL,
  student_uid  text NOT NULL,
  enrolled_at  timestamptz NOT NULL DEFAULT now(),
  removed_at   timestamptz,
  PRIMARY KEY (class_id, student_uid),
  FOREIGN KEY (class_id, school_id) REFERENCES public.classes(id, school_id) ON DELETE CASCADE,
  FOREIGN KEY (student_uid, school_id) REFERENCES public.school_students(uid, school_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS class_enrollments_student_idx
  ON public.class_enrollments (student_uid) WHERE removed_at IS NULL;

-- ── 4. Changes to existing tables ────────────────────────────────────────────

-- A school course is a journeys row owned by the school (uid NULL), so deleting
-- a teacher's account never touches it. Its published state lives in
-- journeys.steps + locked step_content; drafts live in course_versions.
ALTER TABLE public.journeys ADD COLUMN IF NOT EXISTS school_id uuid REFERENCES public.schools(id);
CREATE INDEX IF NOT EXISTS journeys_school_idx ON public.journeys (school_id) WHERE school_id IS NOT NULL;
-- Lets child tables reference (journey id, school id) pairs.
CREATE UNIQUE INDEX IF NOT EXISTS journeys_id_school_key ON public.journeys (id, school_id);

DO $$
BEGIN
  -- D11: school courses can never enter the marketplace.
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'journeys_school_private') THEN
    ALTER TABLE public.journeys
      ADD CONSTRAINT journeys_school_private CHECK (school_id IS NULL OR marketplace_status = 'private');
  END IF;
END $$;

-- Teacher-published step content is locked: automatic regeneration must never
-- overwrite it (README §3.5, invariant I5).
ALTER TABLE public.step_content
  ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'ai',
  ADD COLUMN IF NOT EXISTS locked boolean NOT NULL DEFAULT false;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'step_content_source_check') THEN
    ALTER TABLE public.step_content
      ADD CONSTRAINT step_content_source_check CHECK (source IN ('ai', 'school_published'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conname = 'users_profile_type_check'
       AND pg_get_constraintdef(oid) LIKE '%school_student%'
  ) THEN
    ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_profile_type_check;
    ALTER TABLE public.users
      ADD CONSTRAINT users_profile_type_check
      CHECK (profile_type IN ('account', 'profile', 'school_student'));
  END IF;
END $$;

-- ── 5. Courses (published state in journeys; drafts and history here) ───────

CREATE TABLE IF NOT EXISTS public.school_courses (
  journey_id         text PRIMARY KEY,
  school_id          uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  status             text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  published_version  integer,
  created_by         text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  archived_at        timestamptz,
  UNIQUE (journey_id, school_id),
  FOREIGN KEY (journey_id, school_id) REFERENCES public.journeys(id, school_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS school_courses_school_idx ON public.school_courses (school_id, status);

CREATE TABLE IF NOT EXISTS public.course_versions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  journey_id      text NOT NULL REFERENCES public.school_courses(journey_id) ON DELETE CASCADE,
  version         integer NOT NULL CHECK (version >= 1),
  state           text NOT NULL CHECK (state IN ('draft', 'published', 'superseded', 'discarded')),
  revision        integer NOT NULL DEFAULT 0,      -- optimistic lock for concurrent editors
  meta            jsonb NOT NULL DEFAULT '{}'::jsonb,
  steps           jsonb NOT NULL DEFAULT '[]'::jsonb,
  base_version    integer,
  change_summary  text,
  created_by      text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  published_by    text REFERENCES public.users(uid) ON DELETE SET NULL,
  published_at    timestamptz,
  UNIQUE (journey_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS course_versions_one_draft
  ON public.course_versions (journey_id) WHERE state = 'draft';

-- ── 6. Source material ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.source_documents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id     uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  uploaded_by   text REFERENCES public.users(uid) ON DELETE SET NULL,
  filename      text NOT NULL,
  mime          text NOT NULL,
  size_bytes    bigint CHECK (size_bytes >= 0),
  sha256        text,
  storage_path  text,
  page_count    integer,
  language      text,
  status        text NOT NULL DEFAULT 'pending_upload'
                CHECK (status IN ('pending_upload', 'uploaded', 'extracting', 'ready',
                                  'needs_ocr', 'failed', 'deleted')),
  error_code    text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz,
  UNIQUE (id, school_id)
);
CREATE INDEX IF NOT EXISTS source_documents_school_idx ON public.source_documents (school_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS source_documents_school_sha_key
  ON public.source_documents (school_id, sha256) WHERE sha256 IS NOT NULL AND status <> 'deleted';

CREATE TABLE IF NOT EXISTS public.document_chunks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   uuid NOT NULL REFERENCES public.source_documents(id) ON DELETE CASCADE,
  ordinal       integer NOT NULL,
  heading_path  text[] NOT NULL DEFAULT '{}',
  page_start    integer,
  page_end      integer,
  text          text NOT NULL,
  char_count    integer NOT NULL,
  UNIQUE (document_id, ordinal)
);

CREATE TABLE IF NOT EXISTS public.course_sources (
  journey_id   text NOT NULL,
  document_id  uuid NOT NULL,
  school_id    uuid NOT NULL,
  added_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (journey_id, document_id),
  FOREIGN KEY (journey_id, school_id) REFERENCES public.school_courses(journey_id, school_id) ON DELETE CASCADE,
  FOREIGN KEY (document_id, school_id) REFERENCES public.source_documents(id, school_id) ON DELETE CASCADE
);

-- ── 7. Delivery ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.course_assignments (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id    uuid NOT NULL,
  class_id     uuid NOT NULL,
  journey_id   text NOT NULL,
  assigned_by  text REFERENCES public.users(uid) ON DELETE SET NULL,
  assigned_at  timestamptz NOT NULL DEFAULT now(),
  due_at       timestamptz,
  status       text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
  settings     jsonb NOT NULL DEFAULT '{}'::jsonb,
  archived_at  timestamptz,
  FOREIGN KEY (class_id, school_id) REFERENCES public.classes(id, school_id) ON DELETE CASCADE,
  FOREIGN KEY (journey_id, school_id) REFERENCES public.school_courses(journey_id, school_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS course_assignments_active_key
  ON public.course_assignments (class_id, journey_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS course_assignments_journey_idx
  ON public.course_assignments (journey_id) WHERE status = 'active';

-- ── 8. Jobs, proposals, money, audit ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.school_jobs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id         uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  kind              text NOT NULL CHECK (kind IN ('extract', 'ocr', 'outline', 'build',
                                                  'regenerate_step', 'propose_update')),
  status            text NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
  progress          jsonb NOT NULL DEFAULT '{}'::jsonb,
  result            jsonb,
  attempts          smallint NOT NULL DEFAULT 0,
  max_attempts      smallint NOT NULL DEFAULT 3,
  run_after         timestamptz NOT NULL DEFAULT now(),
  cancel_requested  boolean NOT NULL DEFAULT false,
  locked_at         timestamptz,
  locked_by         text,
  error             text,
  created_by        text REFERENCES public.users(uid) ON DELETE SET NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  started_at        timestamptz,
  finished_at       timestamptz
);
CREATE INDEX IF NOT EXISTS school_jobs_queue_idx ON public.school_jobs (run_after) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS school_jobs_school_idx ON public.school_jobs (school_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.course_change_proposals (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  journey_id  text NOT NULL REFERENCES public.school_courses(journey_id) ON DELETE CASCADE,
  job_id      uuid REFERENCES public.school_jobs(id) ON DELETE SET NULL,
  version     integer NOT NULL,                      -- the draft version it targets
  op          text NOT NULL CHECK (op IN ('add', 'modify', 'remove', 'move')),
  step_id     text,
  payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
  reason      text,
  status      text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
  decided_by  text REFERENCES public.users(uid) ON DELETE SET NULL,
  decided_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS course_change_proposals_course_idx
  ON public.course_change_proposals (journey_id, version);

CREATE TABLE IF NOT EXISTS public.school_usage (
  school_id      uuid NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
  period_start   date NOT NULL,
  cost_cents     numeric NOT NULL DEFAULT 0,
  input_tokens   bigint NOT NULL DEFAULT 0,
  output_tokens  bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (school_id, period_start)
);

-- No FK to schools: the audit trail outlives a deleted school (README §3.12).
CREATE TABLE IF NOT EXISTS public.school_audit_log (
  id           bigserial PRIMARY KEY,
  school_id    uuid NOT NULL,
  actor_uid    text,
  action       text NOT NULL,
  target_type  text,
  target_id    text,
  meta         jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS school_audit_log_school_idx ON public.school_audit_log (school_id, created_at DESC);

-- Server-side only tables: no client (anon/authenticated) access.
ALTER TABLE public.schools                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_members          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_invites          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_students         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.classes                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.class_teachers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.class_enrollments       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_courses          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_versions         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_documents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_chunks         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_sources          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_assignments      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_jobs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.course_change_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_usage            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_audit_log        ENABLE ROW LEVEL SECURITY;
