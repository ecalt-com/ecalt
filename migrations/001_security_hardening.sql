-- Security hardening: revoke public EXECUTE on SECURITY DEFINER function,
-- fix two RLS policies that were scoped to the 'public' role instead of 'authenticated'.

-- 1. rls_auto_enable is an event-trigger helper that should never be callable
--    by end users. Supabase had granted EXECUTE to anon + authenticated by default.
REVOKE EXECUTE ON FUNCTION public.rls_auto_enable() FROM anon, authenticated;

-- 2. journey_recommendations SELECT policy was scoped to PUBLIC (includes anon).
--    Auth filter (auth.uid() = uid) made it zero-row safe but it should not be
--    reachable by unauthenticated callers at all.
DROP POLICY IF EXISTS "users can read own recommendations" ON public.journey_recommendations;
CREATE POLICY "users can read own recommendations" ON public.journey_recommendations
  FOR SELECT
  TO authenticated
  USING ((auth.uid())::text = uid);

-- 3. usage_by_interaction SELECT policy had the same PUBLIC-role issue.
DROP POLICY IF EXISTS "users_read_own_usage" ON public.usage_by_interaction;
CREATE POLICY "users_read_own_usage" ON public.usage_by_interaction
  FOR SELECT
  TO authenticated
  USING ((auth.uid())::text = uid);
