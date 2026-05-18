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
  ('daily_chat',           'openai', 'gpt-4.1-nano'),
  ('nudge',                'openai', 'gpt-4.1-nano'),
  ('onboarding',           'openai', 'gpt-4o-mini'),
  ('fingerprint',          'openai', 'gpt-4o-mini'),
  ('mind_signature',       'openai', 'gpt-4o-mini'),
  ('spark',                'openai', 'gpt-4.1-nano'),
  ('daily_spark',          'openai', 'gpt-4.1-nano'),
  ('knowledge_extraction', 'openai', 'gpt-4.1-nano'),
  ('journey',              'openai', 'gpt-4o-mini'),
  ('step_content',         'openai', 'gpt-4o-mini')
ON CONFLICT (interaction_type) DO NOTHING;

-- Add model_used column to conversation_messages (tracks which model answered)
ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS model_used text;
```
