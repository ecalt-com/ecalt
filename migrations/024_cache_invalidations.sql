-- E1 (plans/feature-improvements): with several uvicorn workers, a change made in
-- one worker must evict the other workers' in-process caches (account status,
-- profile access, school membership, journey access, identity). Workers publish
-- a row here and poll for rows newer than the last one they saw.
CREATE TABLE IF NOT EXISTS public.cache_invalidations (
  seq  bigserial   PRIMARY KEY,
  kind text        NOT NULL,
  key  text        NOT NULL,
  at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS cache_invalidations_at_idx ON public.cache_invalidations (at);
ALTER TABLE public.cache_invalidations ENABLE ROW LEVEL SECURITY;
