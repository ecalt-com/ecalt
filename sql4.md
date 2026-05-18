# Phase 4 SQL — Run in Supabase SQL Editor

```sql
-- AI provider config per interaction type
CREATE TABLE IF NOT EXISTS ai_provider_config (
  interaction_type text primary key,
  provider text not null default 'anthropic',
  model text not null,
  updated_at timestamptz default now()
);

-- Seed with current defaults (safe to re-run)
INSERT INTO ai_provider_config (interaction_type, provider, model) VALUES
  ('daily_chat',     'anthropic', 'claude-haiku-4-5-20251001'),
  ('nudge',          'anthropic', 'claude-haiku-4-5-20251001'),
  ('onboarding',     'anthropic', 'claude-sonnet-4-6'),
  ('fingerprint',    'anthropic', 'claude-sonnet-4-6'),
  ('mind_signature', 'anthropic', 'claude-sonnet-4-6')
ON CONFLICT (interaction_type) DO NOTHING;

-- Add model_used column to conversation_messages (tracks which model answered)
ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS model_used text;
```
