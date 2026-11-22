-- F0.1 (plans/feature-improvements): notification queue hardening.
-- Quiet-hours deferral used to insert a copy AND re-queue the original, and
-- cap-blocked rows were retried forever, so one user's backlog (~141k rows)
-- starved every other user's notifications. Rows now carry an attempt count,
-- an expiry and a claim time, and single-instance types get a unique index.
ALTER TABLE public.notification_queue
  ADD COLUMN IF NOT EXISTS attempts   integer     NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS claimed_at timestamptz;

-- Clean up before the unique index can be created. Idempotent.
UPDATE public.notification_queue SET status = 'expired'
 WHERE status = 'pending' AND notification_type = 'cliffhanger_return'
   AND created_at < now() - interval '48 hours';

UPDATE public.notification_queue q SET status = 'expired'
  FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY uid, notification_type ORDER BY created_at DESC) rn
          FROM public.notification_queue
         WHERE status = 'pending'
           AND notification_type IN ('cliffhanger_return','weekly_digest','re_engagement',
                                     'streak_at_risk','streak_lost','mind_signature_nudge')) d
 WHERE q.id = d.id AND d.rn > 1;

DELETE FROM public.notification_queue
 WHERE status IN ('cancelled','expired','sent','failed') AND created_at < now() - interval '30 days';

CREATE UNIQUE INDEX IF NOT EXISTS notification_queue_one_pending
  ON public.notification_queue (uid, notification_type)
  WHERE status = 'pending' AND notification_type IN
    ('cliffhanger_return','weekly_digest','re_engagement','streak_at_risk','streak_lost','mind_signature_nudge');
