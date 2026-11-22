-- F1.4: click tracking for notification links (opened_at already exists).
ALTER TABLE public.notification_log ADD COLUMN IF NOT EXISTS clicked_at timestamptz;
